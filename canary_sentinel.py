#!/usr/bin/env python3
"""Sentinelle canari : inotify sur des repertoires-appats, arret immediat au premier evenement.

Rien n'est jamais cree ni modifie legitimement dans un repertoire-appat, donc le
moindre evenement est une alarme sans faux positif. On surveille le REPERTOIRE et
pas seulement les fichiers : un rancongiciel qui ecrit a cote puis supprime
l'original ne declenche aucun evenement de modification sur l'appat.

Au declenchement, dans cet ordre : verrou, coupure de la sortie vers l'edge
Cloudflare, unites systemd, tunnels, serveurs, mail. Le verrou d'abord parce qu'un
redemarrage peut courir contre nous ; le reseau ensuite parce que c'est le chemin
d'entree, et qu'un serveur qui agonise derriere un tunnel coupe n'est joignable
par personne.

Le nom du repertoire-appat commence par un point : les enumerations du hub et du
viewer sautent les noms caches, sans quoi le scan placenta creerait un faux cas.
Il se choisit au deploiement et ne se versionne pas — un nom publie est un nom
qu'un rancongiciel peut apprendre a eviter.

  ./canary_sentinel.py --seed --watch <arbre>/<.nom_appat>
  ./canary_sentinel.py --watch <dir> --watch-read <dir> --port 5004 --tunnels-all
  ./canary_sentinel.py --self-check
  ./canary_sentinel.py --systemd            # unit a coller dans /etc/systemd/system

--watch-read ajoute l'ouverture et la lecture : a reserver aux arbres qu'aucune
sauvegarde ne parcourt, la lecture ayant des auteurs legitimes.
"""
from __future__ import annotations

import argparse
import ctypes
import os
import signal
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

LATCH_ENV = "FOETOPATH_CANARY_LATCH"
LATCH_DEFAULT = "~/.foetopath_canary_tripped"
LATCH_EXIT_CODE = 66  # a mettre en RestartPreventExitStatus, sinon systemd relance en boucle

EDGE_PORT = 7844      # cloudflared <-> edge Cloudflare, en TCP comme en UDP
NFT_TABLE = "canari"

# Tout ce qui peut arriver a un repertoire ou rien n'arrive jamais.
IN_MODIFY, IN_ATTRIB, IN_CLOSE_WRITE = 0x2, 0x4, 0x8
IN_MOVED_FROM, IN_MOVED_TO, IN_CREATE = 0x40, 0x80, 0x100
IN_DELETE, IN_DELETE_SELF, IN_MOVE_SELF = 0x200, 0x400, 0x800
IN_ACCESS, IN_OPEN, IN_Q_OVERFLOW, IN_ISDIR = 0x1, 0x20, 0x4000, 0x40000000
WATCH_MASK = (IN_MODIFY | IN_ATTRIB | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO
              | IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF)
# Personne n'ouvre jamais un appat : la lecture denonce la reconnaissance avant
# le chiffrement. Mais elle est bruyante la ou une sauvegarde passe lire.
READ_MASK = IN_OPEN | IN_ACCESS

_FLAG_NAMES = [
    (IN_CREATE, "create"), (IN_MODIFY, "modify"), (IN_CLOSE_WRITE, "close_write"),
    (IN_DELETE, "delete"), (IN_MOVED_FROM, "moved_from"), (IN_MOVED_TO, "moved_to"),
    (IN_ATTRIB, "attrib"), (IN_DELETE_SELF, "delete_self"), (IN_MOVE_SELF, "move_self"),
    (IN_OPEN, "open"), (IN_ACCESS, "read"), (IN_Q_OVERFLOW, "queue_overflow"),
]

# Contenu plausible : un repertoire vide ou des fichiers vides peuvent etre sautes.
BAITS = {
    "admin_credentials.bak": "[hub]\nuser=admin\nhash=$argon2id$v=19$m=65536,t=3,p=4$\n",
    "recovery_keys.txt": "\n".join(f"RK-{i:04d}-XXXX-XXXX-XXXX" for i in range(64)) + "\n",
    "backup_keys.json": '{"targets": ["nas-01", "nas-02"], "wrapped_key": "%s"}\n' % ("A" * 512),
    "mailing_list.csv": "nom,service,email\n" + "".join(
        f"contact{i:03d},service,contact{i:03d}@exemple.invalid\n" for i in range(256)),
}


def latch_path(cli: str = "") -> Path:
    return Path(os.path.expanduser(cli or os.environ.get(LATCH_ENV) or LATCH_DEFAULT))


def _flags(mask: int) -> str:
    return ",".join(n for bit, n in _FLAG_NAMES if mask & bit) or hex(mask)


def listeners(ports: list[int]) -> list[tuple[int, int]]:
    """[(port, pid)] des processus a l'ecoute. Par PID exact : jamais de pkill -f."""
    out = subprocess.run(["ss", "-Hltnp"], capture_output=True, text=True).stdout
    found = []
    for line in out.splitlines():
        if "pid=" not in line:
            continue
        local = line.split()[3]
        try:
            port = int(local.rsplit(":", 1)[1])
        except (IndexError, ValueError):
            continue
        if port not in ports:
            continue
        for chunk in line.split("pid=")[1:]:
            pid = int(chunk.split(",")[0])
            if pid != os.getpid():
                found.append((port, pid))
    return found


def cloudflared(names: list[str], take_all: bool) -> list[tuple[str, int]]:
    """[(etiquette, pid)] des tunnels vises. On resout le PID exact plutot que pkill -f :
    argv[0] doit etre cloudflared, et le nom doit apparaitre dans la ligne de commande."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            argv = (entry / "cmdline").read_bytes().decode(errors="replace").split("\0")
        except OSError:
            continue  # process disparu entre le listing et la lecture
        if not argv or os.path.basename(argv[0]) != "cloudflared":
            continue
        line = " ".join(argv)
        match = next((n for n in names if n in line), None)
        if take_all or match:
            found.append((match or line.split("--config")[-1].strip() or "cloudflared",
                          int(entry.name)))
    return found


def _kill(resolve, label: str, log) -> list[str]:
    targets = resolve()
    if not targets:
        log(f"  aucun {label} a arreter")
        return []
    done = []
    for tag, pid in targets:
        try:
            os.kill(pid, signal.SIGTERM)
            done.append(f"{label} {tag} pid {pid} SIGTERM")
        except OSError as exc:
            done.append(f"{label} {tag} pid {pid} ECHEC {exc}")
    time.sleep(3)
    for tag, pid in targets:
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
            done.append(f"{label} {tag} pid {pid} SIGKILL")
        except OSError:
            pass
    # Reapparu sous un autre PID = service supervise : le tuer ne suffira jamais.
    # C'est attendu pour les tunnels, et sans consequence — leur sortie est coupee.
    time.sleep(2)
    for tag, pid in resolve():
        done.append(f"{label} {tag} REVENU en pid {pid} — supervise")
    for line in done:
        log(f"  {line}")
    return done


def block_edge(log) -> list[str]:
    """Coupe la sortie vers l'edge Cloudflare. Tuer les tunnels ne suffit pas : ce sont
    des unites Restart=on-failure, et un SIGKILL est un echec — elles reviennent en
    quelques secondes. La regle, elle, tient a travers les redemarrages et vaut pour
    tous les tunnels, y compris ceux ajoutes apres coup : pas d'inventaire a maintenir.
    Table dediee pour ne pas toucher au pare-feu existant, et pour que la levee tienne
    en une commande : nft delete table inet canari."""
    rules = (f"table inet {NFT_TABLE} {{\n"
             f"  chain sortie {{\n"
             f"    type filter hook output priority 0; policy accept;\n"
             f"    tcp dport {EDGE_PORT} drop\n"
             f"    udp dport {EDGE_PORT} drop\n"
             f"  }}\n}}\n")
    try:
        r = subprocess.run(["nft", "-f", "-"], input=rules, capture_output=True,
                           text=True, timeout=10)
        done = (f"sortie edge Cloudflare ({EDGE_PORT}/tcp+udp) coupee" if r.returncode == 0
                else f"coupure edge EN ECHEC : {r.stderr.strip() or r.returncode}")
    except Exception as exc:   # nft absent ou fige : on continue, le verrou est deja pose
        done = f"coupure edge EN ECHEC : {exc}"
    log(f"  {done}")
    return [done]


def stop_units(units: list[str], log) -> list[str]:
    """systemctl stop : un Restart=always ne rend pas la main a un simple kill."""
    done = []
    for unit in units:
        r = subprocess.run(["systemctl", "stop", unit], capture_output=True, text=True)
        done.append(f"unite {unit} " + ("arretee" if r.returncode == 0
                                        else f"ECHEC {r.stderr.strip() or r.returncode}"))
        log(f"  {done[-1]}")
    return done


def trip(reason: str, latch: Path, ports: list[int], tunnels: list[str], all_tunnels: bool,
         units: list[str], notify: str, mail: str, log) -> None:
    stamp = datetime.now().isoformat(timespec="seconds")
    log(f"[{stamp}] CANARI DECLENCHE — {reason}")

    latch.parent.mkdir(parents=True, exist_ok=True)
    latch.write_text(f"{stamp}\n{reason}\n\nLes serveurs refusent de demarrer tant que ce "
                     f"fichier existe.\nNe le supprimer qu'apres avoir compris l'evenement.\n",
                     encoding="utf-8")
    log(f"  verrou pose : {latch}")

    killed = []
    # Le reseau avant les processus : une fois la sortie coupee, un tunnel qui
    # ressuscite ne joint plus personne, et l'ordre des kills n'a plus d'urgence.
    if all_tunnels:
        killed += block_edge(log)
    killed += stop_units(units, log)
    if tunnels or all_tunnels:
        killed += _kill(lambda: cloudflared(tunnels, all_tunnels), "tunnel", log)
    if ports:
        killed += _kill(lambda: [(f"port {p}", pid) for p, pid in listeners(ports)],
                        "serveur", log)

    if notify and mail:
        body = (f"Canari declenche le {stamp}.\n\n{reason}\n\n"
                f"Verrou : {latch}\n" + "\n".join(killed))
        try:
            subprocess.run([sys.executable, notify, "--subject",
                            "[FoetoPath] CANARI DECLENCHE — serveurs arretes",
                            "--body", body, "--to", mail], timeout=60, check=False)
            log("  mail envoye")
        except Exception as exc:  # le mail ne doit jamais retarder l'arret
            log(f"  mail en echec : {exc}")


def watch(dirs: list[tuple[Path, int]], on_event, log) -> None:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    fd = libc.inotify_init1(0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), "inotify_init1")
    where = {}
    for d, mask in dirs:
        wd = libc.inotify_add_watch(fd, str(d).encode(), mask)
        if wd < 0:
            raise OSError(ctypes.get_errno(), f"inotify_add_watch {d}")
        where[wd] = d
        log(f"  surveille {d}" + (" (+ lectures)" if mask & READ_MASK else ""))
    while True:
        buf = os.read(fd, 4096)
        off = 0
        while off < len(buf):
            wd, mask, _cookie, nlen = struct.unpack_from("iIII", buf, off)
            off += 16
            name = buf[off:off + nlen].split(b"\0", 1)[0].decode(errors="replace")
            off += nlen
            # Parcourir un arbre ouvre chaque repertoire : du, ls et rsync le font
            # tous les soirs. Seule la lecture d'un FICHIER est significative.
            if mask & IN_ISDIR and not mask & WATCH_MASK:
                continue
            on_event(f"{_flags(mask)} sur {name or '<le repertoire lui-meme>'} "
                     f"dans {where.get(wd, '?')}")
            return  # un seul evenement suffit, on ne revient jamais en surveillance


def seed(dirs: list[Path], log) -> None:
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        for name, content in BAITS.items():
            (d / name).write_text(content, encoding="utf-8")
        log(f"  appats poses dans {d}")


SYSTEMD = """\
[Unit]
Description=FoetoPath — sentinelle canari anti-rancongiciel
After=network.target

[Service]
User={user}
ExecStart={python} {script} {args}
Restart=always
RestartSec=5
# Canari deja declenche : la sentinelle sort en {code} et systemd doit la laisser
# tranquille, sinon on boucle a l'infini sur un verrou pose.
RestartPreventExitStatus={code}

[Install]
WantedBy=multi-user.target
"""

# Le verrou est un fichier, il survit au redemarrage ; la table nftables vit en
# memoire et disparait. Sans cette unite, un reboot rouvre les tunnels alors que le
# canari est toujours declenche — et c'est le pire des etats, celui ou l'on croit
# tout ferme. La condition porte sur le verrou : le jour ou on le leve, l'unite
# redevient muette d'elle-meme, rien de plus a defaire.
SYSTEMD_BOOT = """\
[Unit]
Description=FoetoPath — canari : coupure reseau maintenue apres redemarrage
ConditionPathExists={latch}

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={python} {script} --block-edge

[Install]
WantedBy=multi-user.target
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--watch", action="append", default=[], help="repertoire-appat (repetable)")
    ap.add_argument("--watch-read", action="append", default=[],
                    help="idem, mais declenche AUSSI a la simple lecture d'un appat "
                         "(repetable) — a reserver aux arbres qu'aucune sauvegarde ne lit")
    ap.add_argument("--port", action="append", type=int, default=[],
                    help="port dont le processus a l'ecoute est arrete (repetable)")
    ap.add_argument("--tunnel", action="append", default=[],
                    help="tunnel cloudflared a couper, par nom ou fragment de config (repetable)")
    ap.add_argument("--tunnels-all", action="store_true",
                    help="couper tous les tunnels cloudflared de la machine")
    ap.add_argument("--unit", action="append", default=[],
                    help="unite systemd a arreter par systemctl (repetable) — un Restart=always "
                         "ne rend pas la main a un kill")
    ap.add_argument("--latch", default="", help=f"verrou (defaut {LATCH_DEFAULT})")
    ap.add_argument("--notify", default="", help="chemin de 08_notify.py")
    ap.add_argument("--mail", default="", help="destinataire de l'alerte")
    ap.add_argument("--seed", action="store_true", help="poser les appats et sortir")
    ap.add_argument("--block-edge", action="store_true",
                    help="poser la regle de coupure reseau et sortir (unite de redemarrage)")
    ap.add_argument("--systemd", action="store_true", help="afficher les units systemd et sortir")
    ap.add_argument("--self-check", action="store_true", help="test de bout en bout et sortir")
    args = ap.parse_args()

    def log(msg):
        print(msg, flush=True)

    if args.self_check:
        return self_check(log)
    if args.block_edge:
        return 1 if "ECHEC" in block_edge(log)[0] else 0
    if args.systemd:
        rest = [a for a in sys.argv[1:] if a != "--systemd"]
        print("### /etc/systemd/system/canari.service")
        print(SYSTEMD.format(user=os.environ.get("USER", "mathevet"), python=sys.executable,
                             script=Path(__file__).resolve(), args=" ".join(rest),
                             code=LATCH_EXIT_CODE))
        print("### /etc/systemd/system/canari-coupure.service  (systemctl enable canari-coupure)")
        print(SYSTEMD_BOOT.format(latch=latch_path(args.latch), python=sys.executable,
                                  script=Path(__file__).resolve()))
        return 0

    watched = ([(Path(os.path.expanduser(d)), WATCH_MASK) for d in args.watch]
               + [(Path(os.path.expanduser(d)), WATCH_MASK | READ_MASK)
                  for d in args.watch_read])
    if not watched:
        ap.error("au moins un --watch ou --watch-read")
    if args.seed:
        seed([d for d, _ in watched], log)
        return 0

    missing = [d for d, _ in watched if not d.is_dir()]
    if missing:
        ap.error(f"repertoires absents (poser les appats avec --seed) : {missing}")

    latch = latch_path(args.latch)
    if latch.exists():
        log(f"Le verrou {latch} existe deja — canari deja declenche, rien a surveiller.")
        return LATCH_EXIT_CODE

    log(f"Sentinelle active. Verrou prevu : {latch}")
    watch(watched, lambda reason: trip(reason, latch, args.port, args.tunnel, args.tunnels_all,
                                       args.unit, args.notify, args.mail, log), log)
    return 1  # on ne sort de watch() que declenche


def self_check(log) -> int:
    """Prouve la chaine complete : evenement inotify -> verrou pose."""
    import tempfile
    import threading

    with tempfile.TemporaryDirectory() as tmp:
        bait, latch = Path(tmp) / "appat", Path(tmp) / "verrou"
        seed([bait], log)
        fired = []

        def arm(mask, react=True):
            """react=False pour les cas qui ne doivent PAS declencher : le veilleur
            leur survit, et il reposerait le verrou en voyant le menage de fin."""
            fired.clear()
            if latch.exists():
                latch.unlink()

            def on_event(r):
                fired.append(r)
                if react:
                    trip(r, latch, [], [], False, [], "", "", log)

            t = threading.Thread(target=watch, args=([(bait, mask)], on_event, log), daemon=True)
            t.start()
            time.sleep(0.3)
            return t

        t = arm(WATCH_MASK)
        (bait / "README_RESTORE_FILES.txt").write_text("paye", encoding="utf-8")
        t.join(timeout=5)
        assert fired, "aucun evenement capte"
        assert "create" in fired[0], f"attendu un create, recu {fired[0]}"
        assert latch.exists(), "verrou non pose"
        assert "create" in latch.read_text(), "verrou sans motif"

        # Un fichier deja present qu'on modifie doit aussi declencher.
        t = arm(WATCH_MASK)
        (bait / "recovery_keys.txt").write_text("chiffre", encoding="utf-8")
        t.join(timeout=5)
        assert fired and "modify" in fired[0], f"attendu un modify, recu {fired}"
        assert latch.exists(), "verrou non pose au second tour"

        # Sans --watch-read, lire un appat ne doit RIEN declencher.
        t = arm(WATCH_MASK, react=False)
        (bait / "recovery_keys.txt").read_bytes()
        t.join(timeout=2)
        assert not fired, f"une lecture a declenche le masque ecriture : {fired}"

        # Avec --watch-read, la meme lecture declenche.
        t = arm(WATCH_MASK | READ_MASK)
        (bait / "recovery_keys.txt").read_bytes()
        t.join(timeout=5)
        assert fired and ("open" in fired[0] or "read" in fired[0]), \
            f"attendu open/read, recu {fired}"

        # Mais enumerer le repertoire, ce que fait le du de la purge FIFO chaque
        # nuit, ne doit pas declencher : c'est une ouverture de REPERTOIRE.
        t = arm(WATCH_MASK | READ_MASK, react=False)
        list(bait.iterdir())
        t.join(timeout=2)
        assert not fired, f"un simple parcours a declenche : {fired}"

    log("self-check OK — create/modify declenchent ; la lecture seulement sous "
        "--watch-read, et jamais le parcours du repertoire")
    return 0


if __name__ == "__main__":
    sys.exit(main())
