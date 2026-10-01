from utils.file_ops import list_slides_in


def test_dossier_dcm_est_une_lame(tmp_path):
    (tmp_path / "25P1234_1_1.mrxs").write_bytes(b"")
    (tmp_path / "25P1234_2_1").mkdir()
    (tmp_path / "25P1234_2_1" / "DCM_0.dcm").write_bytes(b"")
    (tmp_path / "superpixels").mkdir()          # dossier sans .dcm : ignoré
    slides = {s["name"]: s for s in list_slides_in(str(tmp_path))}
    assert set(slides) == {"25P1234_1_1", "25P1234_2_1"}
    assert slides["25P1234_2_1"]["path"] == str(tmp_path / "25P1234_2_1")
    assert slides["25P1234_2_1"]["extension"] == ".dcm"
