/* ═══ FoetoPath — Reference Data Tables ═══ */
/*
 * Sources:
 * - GC: Guihard-Costa et al. 2002 (biométries + organes 13-42 SA, bi-hebdomadaire)
 * - MA: Maroun (biométries 12-43 SA entières)
 * - MB_BIO: Muller-Brochut et al. 2018 (biométries 12-20 SA)
 * - MA_ORG: Maroun (organes 12-43 SA, par grade macération 0-1/2/3)
 * - MB_ORG: Muller-Brochut et al. 2018 (organes 12-20 SA)
 * - GC_ORG: Guihard-Costa et al. 2002 (organes 13-42 SA, bi-hebdomadaire)
 *
 * Maroun biométries keys: B=Body(g), F=Foot(mm), C=CR(cm), H=CH(cm), D=HDC(cm)
 * Maroun organes: brain, heart (single), liver_01/2/3, lungs_01/23, thymus_01/2/3,
 *   spleen_01/23, kidneys_01/23, adrenals_01/23
 */

// ═══ GUIHARD-COSTA 2002 — Biométries (bi-hebdomadaire) ═══
// masse(g), VT(mm), VC(mm), PC(mm), pied(mm)
var GC = {
  "13-14":{masse:{m:55.8,sd:14.4},VT:{m:131.8,sd:15.4},VC:{m:89.6,sd:11.7},PC:{m:89.2,sd:11.8},pied:{m:14,sd:2.9}},
  "15-16":{masse:{m:108.6,sd:24.7},VT:{m:170.4,sd:16.2},VC:{m:116.2,sd:12.2},PC:{m:116.7,sd:12.2},pied:{m:19,sd:3}},
  "17-18":{masse:{m:176.1,sd:39},VT:{m:207.4,sd:17},VC:{m:141.7,sd:12.7},PC:{m:142.8,sd:12.6},pied:{m:25,sd:3.2}},
  "19-20":{masse:{m:267.7,sd:57.1},VT:{m:242.9,sd:17.8},VC:{m:166.2,sd:13.1},PC:{m:167.5,sd:12.9},pied:{m:30,sd:3.3}},
  "21-22":{masse:{m:392.7,sd:79.2},VT:{m:276.8,sd:18.6},VC:{m:189.8,sd:13.6},PC:{m:190.9,sd:13.3},pied:{m:36,sd:3.5}},
  "23-24":{masse:{m:559.6,sd:105.1},VT:{m:309.2,sd:19.4},VC:{m:212.3,sd:14.1},PC:{m:212.8,sd:13.7},pied:{m:42,sd:3.6}},
  "25-26":{masse:{m:773.9,sd:134.9},VT:{m:340,sd:20.2},VC:{m:233.8,sd:14.6},PC:{m:233.4,sd:14},pied:{m:48,sd:3.8}},
  "27-28":{masse:{m:1038.2,sd:168.6},VT:{m:369.3,sd:21},VC:{m:254.4,sd:15.1},PC:{m:252.7,sd:14.4},pied:{m:53,sd:3.9}},
  "29-30":{masse:{m:1350.4,sd:206.1},VT:{m:397,sd:21.8},VC:{m:273.9,sd:15.5},PC:{m:270.5,sd:14.8},pied:{m:58,sd:4.1}},
  "31-32":{masse:{m:1702.5,sd:247.6},VT:{m:432.2,sd:22.6},VC:{m:292.4,sd:16},PC:{m:287,sd:15.1},pied:{m:63,sd:4.2}},
  "33-34":{masse:{m:2080.2,sd:292.9},VT:{m:447.8,sd:23.4},VC:{m:309.9,sd:16.5},PC:{m:302.1,sd:15.5},pied:{m:67,sd:4.4}},
  "35-36":{masse:{m:2460.8,sd:342.1},VT:{m:470.9,sd:24.2},VC:{m:326.5,sd:17},PC:{m:315.8,sd:15.9},pied:{m:71,sd:4.6}},
  "37-38":{masse:{m:2813.1,sd:395.3},VT:{m:492.5,sd:24.9},VC:{m:342,sd:17.5},PC:{m:328.1,sd:16.2},pied:{m:74,sd:4.7}},
  "39-40":{masse:{m:3095.1,sd:452.2},VT:{m:512.5,sd:25.7},VC:{m:356,sd:17.9},PC:{m:339.1,sd:16.6},pied:{m:77,sd:4.9}},
  "41-42":{masse:{m:3268.8,sd:512.7},VT:{m:531.1,sd:26.5},VC:{m:369,sd:18.4},PC:{m:348.8,sd:16.9},pied:{m:80,sd:5}}
};

// ═══ MAROUN — Biométries (SA entières 12-43) ═══
// B=Body(g), F=Foot(mm), C=CR(cm), H=CH(cm), D=HDC(cm)
var MA = [
  {s:12,B:{m:29.6,sd:14.9},F:{m:9,sd:3},C:{m:7.4,sd:1.1},H:{m:9.8,sd:1.7},D:{m:7.1,sd:1.1}},
  {s:13,B:{m:37.4,sd:14.9},F:{m:12,sd:3},C:{m:8.7,sd:1.2},H:{m:11.8,sd:1.8},D:{m:8.5,sd:1.2}},
  {s:14,B:{m:53,sd:14.9},F:{m:15,sd:3},C:{m:9.9,sd:1.2},H:{m:13.7,sd:1.8},D:{m:9.8,sd:1.2}},
  {s:15,B:{m:76.5,sd:18.5},F:{m:18,sd:3},C:{m:11.1,sd:1.2},H:{m:15.6,sd:1.8},D:{m:11.1,sd:1.2}},
  {s:16,B:{m:108,sd:41},F:{m:21,sd:3},C:{m:12.4,sd:1.3},H:{m:17.5,sd:1.8},D:{m:12.4,sd:1.3}},
  {s:17,B:{m:147,sd:53},F:{m:24,sd:3},C:{m:13.5,sd:1.3},H:{m:19.3,sd:1.9},D:{m:13.6,sd:1.3}},
  {s:18,B:{m:194,sd:65},F:{m:27,sd:3},C:{m:14.7,sd:1.3},H:{m:21.1,sd:1.9},D:{m:14.8,sd:1.3}},
  {s:19,B:{m:249,sd:78},F:{m:30,sd:3},C:{m:15.9,sd:1.3},H:{m:22.9,sd:1.9},D:{m:16,sd:1.3}},
  {s:20,B:{m:312,sd:92},F:{m:33,sd:3},C:{m:17,sd:1.4},H:{m:24.6,sd:1.9},D:{m:17.2,sd:1.4}},
  {s:21,B:{m:382,sd:107},F:{m:36,sd:3},C:{m:18.2,sd:1.4},H:{m:26.3,sd:2},D:{m:18.3,sd:1.4}},
  {s:22,B:{m:461,sd:122},F:{m:39,sd:3},C:{m:19.3,sd:1.4},H:{m:28,sd:2},D:{m:19.4,sd:1.4}},
  {s:23,B:{m:547,sd:122},F:{m:41,sd:4},C:{m:20.4,sd:1.5},H:{m:29.6,sd:2},D:{m:20.5,sd:1.4}},
  {s:24,B:{m:641,sd:137},F:{m:44,sd:4},C:{m:21.5,sd:1.5},H:{m:31.2,sd:2},D:{m:21.6,sd:1.5}},
  {s:25,B:{m:743,sd:154},F:{m:47,sd:4},C:{m:22.6,sd:1.5},H:{m:32.8,sd:2.1},D:{m:22.6,sd:1.5}},
  {s:26,B:{m:853,sd:171},F:{m:50,sd:4},C:{m:23.6,sd:1.5},H:{m:34.3,sd:2.1},D:{m:23.6,sd:1.5}},
  {s:27,B:{m:971,sd:188},F:{m:52,sd:4},C:{m:24.7,sd:1.6},H:{m:35.8,sd:2.1},D:{m:24.5,sd:1.5}},
  {s:28,B:{m:1096,sd:206},F:{m:55,sd:4},C:{m:25.7,sd:1.6},H:{m:37.3,sd:2.2},D:{m:25.5,sd:1.6}},
  {s:29,B:{m:1230,sd:225},F:{m:57,sd:4},C:{m:26.7,sd:1.6},H:{m:38.7,sd:2.2},D:{m:26.4,sd:1.6}},
  {s:30,B:{m:1371,sd:244},F:{m:60,sd:4},C:{m:27.7,sd:1.6},H:{m:40.1,sd:2.2},D:{m:27.2,sd:1.6}},
  {s:31,B:{m:1520,sd:264},F:{m:62,sd:4},C:{m:28.7,sd:1.7},H:{m:41.4,sd:2.2},D:{m:28.1,sd:1.7}},
  {s:32,B:{m:1677,sd:285},F:{m:64,sd:4},C:{m:29.7,sd:1.7},H:{m:42.8,sd:2.3},D:{m:28.9,sd:1.7}},
  {s:33,B:{m:1842,sd:306},F:{m:67,sd:4},C:{m:30.6,sd:1.7},H:{m:44,sd:2.3},D:{m:29.7,sd:1.7}},
  {s:34,B:{m:2015,sd:328},F:{m:69,sd:4},C:{m:31.6,sd:1.8},H:{m:45.3,sd:2.3},D:{m:30.5,sd:1.7}},
  {s:35,B:{m:2195,sd:350},F:{m:71,sd:5},C:{m:32.5,sd:1.8},H:{m:46.5,sd:2.3},D:{m:31.2,sd:1.8}},
  {s:36,B:{m:2383,sd:373},F:{m:73,sd:5},C:{m:33.4,sd:1.8},H:{m:47.7,sd:2.4},D:{m:31.9,sd:1.8}},
  {s:37,B:{m:2580,sd:397},F:{m:76,sd:5},C:{m:34.3,sd:1.8},H:{m:48.9,sd:2.4},D:{m:32.6,sd:1.8}},
  {s:38,B:{m:2784,sd:421},F:{m:78,sd:5},C:{m:35.2,sd:1.9},H:{m:50,sd:2.4},D:{m:33.2,sd:1.8}},
  {s:39,B:{m:2996,sd:446},F:{m:80,sd:5},C:{m:36.1,sd:1.9},H:{m:51.1,sd:2.4},D:{m:33.8,sd:1.9}},
  {s:40,B:{m:3215,sd:471},F:{m:82,sd:5},C:{m:37,sd:1.9},H:{m:52.1,sd:2.5},D:{m:34.4,sd:1.9}},
  {s:41,B:{m:3443,sd:497},F:{m:84,sd:5},C:{m:37.8,sd:1.9},H:{m:53.1,sd:2.5},D:{m:35,sd:1.9}},
  {s:42,B:{m:3678,sd:524},F:{m:86,sd:5},C:{m:38.6,sd:2},H:{m:54.1,sd:2.5},D:{m:35.5,sd:2}},
  {s:43,B:{m:3922,sd:551},F:{m:88,sd:5},C:{m:39.4,sd:2},H:{m:55,sd:2.5},D:{m:36,sd:2}}
];

// ═══ MULLER-BROCHUT 2018 — Biométries (12-20 SA) ═══
// All values in cm except Fetus in g
var MB_BIO = {
  12:{CRL:{m:6.82,sd:.73},CFL:{m:8.85,sd:1},HC:{m:7.03,sd:.69},TC:{m:5.97,sd:.68},AC:{m:5.32,sd:.76},Foot:{m:.9,sd:.12},Hand:{m:.84,sd:.14},BPD:{m:2,sd:1},FOD:{m:2.72,sd:.32},Fetus:{m:17.86,sd:4.8}},
  13:{CRL:{m:7.99,sd:.78},CFL:{m:11.11,sd:1.02},HC:{m:7.99,sd:.82},TC:{m:6.72,sd:.57},AC:{m:5.51,sd:.72},Foot:{m:1.15,sd:.11},Hand:{m:1,sd:.11},BPD:{m:2.24,sd:.19},FOD:{m:2.85,sd:.23},Fetus:{m:28.11,sd:6.41}},
  14:{CRL:{m:9.51,sd:.82},CFL:{m:13.2,sd:1.19},HC:{m:9.2,sd:.89},TC:{m:7.81,sd:.62},AC:{m:6.56,sd:.8},Foot:{m:1.42,sd:.19},Hand:{m:1.27,sd:.16},BPD:{m:2.55,sd:.19},FOD:{m:3.31,sd:.17},Fetus:{m:45.88,sd:10.58}},
  15:{CRL:{m:10.67,sd:.83},CFL:{m:15.34,sd:1.2},HC:{m:10.78,sd:1.21},TC:{m:9.08,sd:.79},AC:{m:7.83,sd:1.36},Foot:{m:1.72,sd:.19},Hand:{m:1.52,sd:.19},BPD:{m:3.04,sd:.25},FOD:{m:3.71,sd:.24},Fetus:{m:69.41,sd:13.07}},
  16:{CRL:{m:11.53,sd:1.03},CFL:{m:16.77,sd:1.21},HC:{m:12.01,sd:.72},TC:{m:10.29,sd:.66},AC:{m:8.42,sd:.99},Foot:{m:2.03,sd:.12},Hand:{m:1.75,sd:.21},BPD:{m:3.42,sd:.2},FOD:{m:4.19,sd:.22},Fetus:{m:98.6,sd:11.6}},
  17:{CRL:{m:12.73,sd:.55},CFL:{m:18.55,sd:.9},HC:{m:13.27,sd:.79},TC:{m:11.11,sd:.79},AC:{m:8.56,sd:1.05},Foot:{m:2.34,sd:.14},Hand:{m:1.97,sd:.16},BPD:{m:3.63,sd:.23},FOD:{m:4.33,sd:.28},Fetus:{m:125.21,sd:17.84}},
  18:{CRL:{m:13.89,sd:.66},CFL:{m:20.49,sd:.65},HC:{m:14.58,sd:.97},TC:{m:11.9,sd:.88},AC:{m:9.45,sd:.76},Foot:{m:2.62,sd:.21},Hand:{m:2.32,sd:.2},BPD:{m:3.89,sd:.36},FOD:{m:4.93,sd:.22},Fetus:{m:172.04,sd:25.16}},
  19:{CRL:{m:15.18,sd:.71},CFL:{m:22.88,sd:1.58},HC:{m:15.82,sd:1.35},TC:{m:12.64,sd:.47},AC:{m:10.34,sd:1.3},Foot:{m:2.95,sd:.18},Hand:{m:2.42,sd:.08},BPD:{m:4.3,sd:.28},FOD:{m:5.44,sd:.32},Fetus:{m:228.47,sd:43.37}},
  20:{CRL:{m:16.67,sd:.46},CFL:{m:25.48,sd:1.23},HC:{m:16.88,sd:.68},TC:{m:14.23,sd:.13},AC:{m:11.97,sd:1.12},Foot:{m:3.31,sd:.18},Hand:{m:2.72,sd:.15},BPD:{m:4.38,sd:.04},FOD:{m:5.93,sd:.04},Fetus:{m:306.5,sd:26.71}}
};

// ═══ MAROUN — Masses d'organes (SA 12-43, par grade macération) ═══
// brain, heart: single ref; liver: _01/_2/_3; lungs/spleen/kidneys/adrenals: _01/_23; thymus: _01/_2/_3
var MA_ORG = [
  {s:12,brain:{m:5.7,sd:1.4},heart:{m:0.2,sd:0.14},liver_01:{m:1.8,sd:1.2},liver_2:{m:1.8,sd:1.2},liver_3:{m:1.8,sd:1.2},lungs_01:{m:1.2,sd:0.9},lungs_23:{m:1.2,sd:0.9},thymus_01:{m:0.04,sd:0.06},thymus_2:{m:0.02,sd:0.03},thymus_3:{m:0.08,sd:0.03},spleen_01:{m:0.3,sd:0.1},spleen_23:{m:0.2,sd:0.1},kidneys_01:{m:0.17,sd:0.18},kidneys_23:{m:0.17,sd:0.18},adrenals_01:{m:null,sd:null},adrenals_23:{m:null,sd:null}},
  {s:13,brain:{m:5.7,sd:1.4},heart:{m:0.2,sd:0.14},liver_01:{m:1.8,sd:1.2},liver_2:{m:1.8,sd:1.2},liver_3:{m:1.8,sd:1.2},lungs_01:{m:1.2,sd:0.9},lungs_23:{m:1.2,sd:0.9},thymus_01:{m:0.04,sd:0.06},thymus_2:{m:0.02,sd:0.03},thymus_3:{m:0.08,sd:0.03},spleen_01:{m:0.3,sd:0.1},spleen_23:{m:0.2,sd:0.1},kidneys_01:{m:0.17,sd:0.18},kidneys_23:{m:0.17,sd:0.18},adrenals_01:{m:null,sd:null},adrenals_23:{m:null,sd:null}},
  {s:14,brain:{m:9.1,sd:2.5},heart:{m:0.3,sd:0.1},liver_01:{m:2.9,sd:1.2},liver_2:{m:2.4,sd:1.2},liver_3:{m:2.3,sd:1.2},lungs_01:{m:2.0,sd:0.9},lungs_23:{m:1.5,sd:0.9},thymus_01:{m:0.05,sd:0.06},thymus_2:{m:0.07,sd:0.06},thymus_3:{m:0.05,sd:0.06},spleen_01:{m:0.04,sd:0.04},spleen_23:{m:0.14,sd:0.04},kidneys_01:{m:0.4,sd:0.1},kidneys_23:{m:0.3,sd:0.1},adrenals_01:{m:0.3,sd:0.2},adrenals_23:{m:0.2,sd:0.2}},
  {s:15,brain:{m:12.7,sd:3.9},heart:{m:0.5,sd:0.1},liver_01:{m:4.2,sd:1.2},liver_2:{m:3.3,sd:1.2},liver_3:{m:3.2,sd:1.2},lungs_01:{m:2.9,sd:0.9},lungs_23:{m:2.1,sd:0.9},thymus_01:{m:0.07,sd:0.06},thymus_2:{m:0.08,sd:0.06},thymus_3:{m:0.06,sd:0.06},spleen_01:{m:0.06,sd:0.06},spleen_23:{m:0.17,sd:0.06},kidneys_01:{m:0.6,sd:0.3},kidneys_23:{m:0.5,sd:0.3},adrenals_01:{m:0.5,sd:0.2},adrenals_23:{m:0.3,sd:0.2}},
  {s:16,brain:{m:17.3,sd:5.4},heart:{m:0.8,sd:0.2},liver_01:{m:5.9,sd:1.5},liver_2:{m:4.5,sd:1.5},liver_3:{m:4.2,sd:1.5},lungs_01:{m:3.9,sd:1.2},lungs_23:{m:2.7,sd:1.2},thymus_01:{m:0.11,sd:0.06},thymus_2:{m:0.12,sd:0.06},thymus_3:{m:0.09,sd:0.06},spleen_01:{m:0.09,sd:0.08},spleen_23:{m:0.17,sd:0.08},kidneys_01:{m:0.9,sd:0.4},kidneys_23:{m:0.8,sd:0.4},adrenals_01:{m:0.6,sd:0.3},adrenals_23:{m:0.4,sd:0.3}},
  {s:17,brain:{m:22.9,sd:6.9},heart:{m:1.0,sd:0.4},liver_01:{m:8.1,sd:3.0},liver_2:{m:6.1,sd:3.0},liver_3:{m:5.4,sd:3.0},lungs_01:{m:5.1,sd:1.7},lungs_23:{m:3.5,sd:1.7},thymus_01:{m:0.18,sd:0.06},thymus_2:{m:0.18,sd:0.06},thymus_3:{m:0.12,sd:0.06},spleen_01:{m:0.13,sd:0.12},spleen_23:{m:0.16,sd:0.12},kidneys_01:{m:1.3,sd:0.6},kidneys_23:{m:1.1,sd:0.6},adrenals_01:{m:0.8,sd:0.4},adrenals_23:{m:0.5,sd:0.4}},
  {s:18,brain:{m:29.4,sd:8.4},heart:{m:1.4,sd:0.5},liver_01:{m:10.7,sd:4.5},liver_2:{m:7.9,sd:4.5},liver_3:{m:6.8,sd:4.5},lungs_01:{m:6.4,sd:2.3},lungs_23:{m:4.4,sd:2.3},thymus_01:{m:0.3,sd:0.2},thymus_2:{m:0.3,sd:0.2},thymus_3:{m:0.2,sd:0.2},spleen_01:{m:0.19,sd:0.17},spleen_23:{m:0.15,sd:0.17},kidneys_01:{m:1.8,sd:0.8},kidneys_23:{m:1.5,sd:0.8},adrenals_01:{m:1.0,sd:0.4},adrenals_23:{m:0.7,sd:0.4}},
  {s:19,brain:{m:37.0,sd:9.8},heart:{m:1.7,sd:0.7},liver_01:{m:13.8,sd:6.0},liver_2:{m:10.1,sd:6.0},liver_3:{m:8.4,sd:6.0},lungs_01:{m:7.9,sd:2.8},lungs_23:{m:5.4,sd:2.8},thymus_01:{m:0.4,sd:0.3},thymus_2:{m:0.4,sd:0.3},thymus_3:{m:0.3,sd:0.3},spleen_01:{m:0.3,sd:0.2},spleen_23:{m:0.15,sd:0.22},kidneys_01:{m:2.4,sd:1.0},kidneys_23:{m:2.0,sd:1.0},adrenals_01:{m:1.2,sd:0.5},adrenals_23:{m:0.8,sd:0.5}},
  {s:20,brain:{m:45.5,sd:11.3},heart:{m:2.1,sd:0.8},liver_01:{m:17.2,sd:7.5},liver_2:{m:12.5,sd:7.5},liver_3:{m:10.2,sd:7.5},lungs_01:{m:9.5,sd:3.4},lungs_23:{m:6.5,sd:3.4},thymus_01:{m:0.6,sd:0.4},thymus_2:{m:0.5,sd:0.4},thymus_3:{m:0.3,sd:0.4},spleen_01:{m:0.4,sd:0.3},spleen_23:{m:0.17,sd:0.29},kidneys_01:{m:3.0,sd:1.2},kidneys_23:{m:2.5,sd:1.2},adrenals_01:{m:1.4,sd:0.6},adrenals_23:{m:1.0,sd:0.6}},
  {s:21,brain:{m:55.0,sd:12.8},heart:{m:2.6,sd:1.0},liver_01:{m:21.1,sd:9.0},liver_2:{m:15.2,sd:9.0},liver_3:{m:12.3,sd:9.0},lungs_01:{m:11.2,sd:4.0},lungs_23:{m:7.8,sd:4.0},thymus_01:{m:0.8,sd:0.5},thymus_2:{m:0.7,sd:0.5},thymus_3:{m:0.4,sd:0.5},spleen_01:{m:0.5,sd:0.4},spleen_23:{m:0.22,sd:0.36},kidneys_01:{m:3.8,sd:1.4},kidneys_23:{m:3.1,sd:1.4},adrenals_01:{m:1.7,sd:0.7},adrenals_23:{m:1.2,sd:0.7}},
  {s:22,brain:{m:65.4,sd:14.3},heart:{m:3.1,sd:1.1},liver_01:{m:25.5,sd:10.4},liver_2:{m:18.2,sd:10.4},liver_3:{m:14.5,sd:10.4},lungs_01:{m:13.1,sd:4.6},lungs_23:{m:9.2,sd:4.6},thymus_01:{m:1.0,sd:0.6},thymus_2:{m:0.9,sd:0.6},thymus_3:{m:0.6,sd:0.6},spleen_01:{m:0.7,sd:0.4},spleen_23:{m:0.3,sd:0.4},kidneys_01:{m:4.6,sd:1.6},kidneys_23:{m:3.8,sd:1.6},adrenals_01:{m:1.9,sd:0.8},adrenals_23:{m:1.4,sd:0.8}},
  {s:23,brain:{m:76.9,sd:15.8},heart:{m:3.6,sd:1.3},liver_01:{m:30.2,sd:11.9},liver_2:{m:21.6,sd:11.9},liver_3:{m:16.9,sd:11.9},lungs_01:{m:15.1,sd:5.3},lungs_23:{m:10.7,sd:5.3},thymus_01:{m:1.3,sd:0.8},thymus_2:{m:1.1,sd:0.8},thymus_3:{m:0.7,sd:0.8},spleen_01:{m:0.9,sd:0.5},spleen_23:{m:0.4,sd:0.5},kidneys_01:{m:5.5,sd:1.8},kidneys_23:{m:4.6,sd:1.8},adrenals_01:{m:2.2,sd:0.9},adrenals_23:{m:1.6,sd:0.9}},
  {s:24,brain:{m:89.3,sd:17.3},heart:{m:4.3,sd:1.5},liver_01:{m:35.4,sd:13.5},liver_2:{m:25.3,sd:13.5},liver_3:{m:19.6,sd:13.5},lungs_01:{m:17.3,sd:6.0},lungs_23:{m:12.3,sd:6.0},thymus_01:{m:1.6,sd:0.9},thymus_2:{m:1.3,sd:0.9},thymus_3:{m:0.8,sd:0.9},spleen_01:{m:1.1,sd:0.6},spleen_23:{m:0.5,sd:0.6},kidneys_01:{m:6.5,sd:2.1},kidneys_23:{m:5.5,sd:2.1},adrenals_01:{m:2.5,sd:1.0},adrenals_23:{m:1.8,sd:1.0}},
  {s:25,brain:{m:102,sd:18.8},heart:{m:5.0,sd:1.6},liver_01:{m:41,sd:15},liver_2:{m:29.3,sd:15},liver_3:{m:22.5,sd:15},lungs_01:{m:19.7,sd:6.7},lungs_23:{m:14,sd:6.7},thymus_01:{m:1.9,sd:1.0},thymus_2:{m:1.6,sd:1.0},thymus_3:{m:1.0,sd:1.0},spleen_01:{m:1.4,sd:0.7},spleen_23:{m:0.7,sd:0.7},kidneys_01:{m:7.6,sd:2.3},kidneys_23:{m:6.4,sd:2.3},adrenals_01:{m:2.8,sd:1.0},adrenals_23:{m:2.1,sd:1.0}},
  {s:26,brain:{m:116,sd:20.3},heart:{m:5.7,sd:1.8},liver_01:{m:47.2,sd:16.6},liver_2:{m:33.7,sd:16.6},liver_3:{m:25.7,sd:16.6},lungs_01:{m:22.2,sd:7.5},lungs_23:{m:15.8,sd:7.5},thymus_01:{m:2.3,sd:1.2},thymus_2:{m:1.9,sd:1.2},thymus_3:{m:1.2,sd:1.2},spleen_01:{m:1.7,sd:0.8},spleen_23:{m:1.0,sd:0.8},kidneys_01:{m:8.8,sd:2.5},kidneys_23:{m:7.4,sd:2.5},adrenals_01:{m:3.1,sd:1.1},adrenals_23:{m:2.3,sd:1.1}},
  {s:27,brain:{m:131,sd:21.8},heart:{m:6.6,sd:1.9},liver_01:{m:53.8,sd:18.3},liver_2:{m:38.4,sd:18.3},liver_3:{m:29,sd:18.3},lungs_01:{m:24.8,sd:8.2},lungs_23:{m:17.8,sd:8.2},thymus_01:{m:2.7,sd:1.3},thymus_2:{m:2.3,sd:1.3},thymus_3:{m:1.4,sd:1.3},spleen_01:{m:2.1,sd:0.9},spleen_23:{m:1.3,sd:0.9},kidneys_01:{m:10,sd:2.8},kidneys_23:{m:8.5,sd:2.8},adrenals_01:{m:3.4,sd:1.2},adrenals_23:{m:2.6,sd:1.2}},
  {s:28,brain:{m:147,sd:23.3},heart:{m:7.5,sd:2.0},liver_01:{m:61,sd:20},liver_2:{m:43.4,sd:20},liver_3:{m:32.5,sd:20},lungs_01:{m:27.5,sd:9},lungs_23:{m:19.9,sd:9},thymus_01:{m:3.2,sd:1.5},thymus_2:{m:2.7,sd:1.5},thymus_3:{m:1.7,sd:1.5},spleen_01:{m:2.5,sd:1.1},spleen_23:{m:1.7,sd:1.1},kidneys_01:{m:11.4,sd:3.1},kidneys_23:{m:9.6,sd:3.1},adrenals_01:{m:3.8,sd:1.3},adrenals_23:{m:2.9,sd:1.3}},
  {s:29,brain:{m:163,sd:24.8},heart:{m:8.5,sd:2.1},liver_01:{m:68.7,sd:21.7},liver_2:{m:48.8,sd:21.7},liver_3:{m:36.2,sd:21.7},lungs_01:{m:30.4,sd:9.8},lungs_23:{m:22.1,sd:9.8},thymus_01:{m:3.7,sd:1.8},thymus_2:{m:3.1,sd:1.8},thymus_3:{m:1.9,sd:1.8},spleen_01:{m:3.0,sd:1.3},spleen_23:{m:2.2,sd:1.3},kidneys_01:{m:12.9,sd:3.4},kidneys_23:{m:10.8,sd:3.4},adrenals_01:{m:4.1,sd:1.3},adrenals_23:{m:3.2,sd:1.3}},
  {s:30,brain:{m:181,sd:26.3},heart:{m:8.5,sd:2.2},liver_01:{m:76.9,sd:23.3},liver_2:{m:54.5,sd:23.3},liver_3:{m:40,sd:23.3},lungs_01:{m:33.3,sd:10.6},lungs_23:{m:24.5,sd:10.6},thymus_01:{m:4.1,sd:2.0},thymus_2:{m:3.4,sd:2.0},thymus_3:{m:2.1,sd:2.0},spleen_01:{m:3.6,sd:1.4},spleen_23:{m:2.7,sd:1.4},kidneys_01:{m:14.5,sd:3.6},kidneys_23:{m:12.1,sd:3.6},adrenals_01:{m:4.5,sd:1.4},adrenals_23:{m:3.5,sd:1.4}},
  {s:31,brain:{m:204,sd:28},heart:{m:9.6,sd:2.4},liver_01:{m:83.9,sd:23.8},liver_2:{m:59,sd:23.8},liver_3:{m:43.4,sd:23.8},lungs_01:{m:36.3,sd:11},lungs_23:{m:27.4,sd:11},thymus_01:{m:4.5,sd:2.3},thymus_2:{m:3.7,sd:2.3},thymus_3:{m:2.3,sd:2.3},spleen_01:{m:4.2,sd:1.6},spleen_23:{m:3.3,sd:1.6},kidneys_01:{m:16,sd:4.3},kidneys_23:{m:13.4,sd:4.3},adrenals_01:{m:4.8,sd:1.5},adrenals_23:{m:3.8,sd:1.5}},
  {s:32,brain:{m:224,sd:29},heart:{m:10.6,sd:2.6},liver_01:{m:92.6,sd:25.3},liver_2:{m:65,sd:25.3},liver_3:{m:47.6,sd:25.3},lungs_01:{m:39.6,sd:11.8},lungs_23:{m:30,sd:11.8},thymus_01:{m:5.0,sd:2.5},thymus_2:{m:4.2,sd:2.5},thymus_3:{m:2.6,sd:2.5},spleen_01:{m:4.8,sd:1.8},spleen_23:{m:3.9,sd:1.8},kidneys_01:{m:17.7,sd:4.6},kidneys_23:{m:14.9,sd:4.6},adrenals_01:{m:5.2,sd:1.6},adrenals_23:{m:4.1,sd:1.6}},
  {s:33,brain:{m:245,sd:31},heart:{m:11.6,sd:2.7},liver_01:{m:102,sd:27},liver_2:{m:71.3,sd:26.7},liver_3:{m:52.1,sd:26.7},lungs_01:{m:43,sd:12.6},lungs_23:{m:32.8,sd:12.6},thymus_01:{m:5.6,sd:2.8},thymus_2:{m:4.6,sd:2.8},thymus_3:{m:2.9,sd:2.8},spleen_01:{m:5.5,sd:1.9},spleen_23:{m:4.5,sd:1.9},kidneys_01:{m:19.5,sd:5},kidneys_23:{m:16.4,sd:5},adrenals_01:{m:5.6,sd:1.7},adrenals_23:{m:4.5,sd:1.7}},
  {s:34,brain:{m:268,sd:32},heart:{m:12.6,sd:2.9},liver_01:{m:111,sd:28},liver_2:{m:77.9,sd:28},liver_3:{m:56.7,sd:28},lungs_01:{m:46.6,sd:13.5},lungs_23:{m:35.7,sd:13.5},thymus_01:{m:6.2,sd:3.1},thymus_2:{m:5.1,sd:3.1},thymus_3:{m:3.2,sd:3.1},spleen_01:{m:6.3,sd:2.1},spleen_23:{m:5.2,sd:2.1},kidneys_01:{m:21.4,sd:5.2},kidneys_23:{m:18,sd:5.2},adrenals_01:{m:6.0,sd:1.8},adrenals_23:{m:4.8,sd:1.8}},
  {s:35,brain:{m:291,sd:33},heart:{m:13.7,sd:3.0},liver_01:{m:121,sd:30},liver_2:{m:84.8,sd:29.7},liver_3:{m:61.5,sd:29.7},lungs_01:{m:50.3,sd:14.3},lungs_23:{m:38.7,sd:14.3},thymus_01:{m:6.9,sd:3.3},thymus_2:{m:5.7,sd:3.3},thymus_3:{m:3.5,sd:3.3},spleen_01:{m:7.2,sd:2.3},spleen_23:{m:6.0,sd:2.3},kidneys_01:{m:23.3,sd:5.8},kidneys_23:{m:19.6,sd:5.8},adrenals_01:{m:6.5,sd:1.9},adrenals_23:{m:5.2,sd:1.9}},
  {s:36,brain:{m:315,sd:35},heart:{m:14.8,sd:3.2},liver_01:{m:132,sd:31},liver_2:{m:92.1,sd:31.2},liver_3:{m:66.5,sd:31.2},lungs_01:{m:54.1,sd:15.2},lungs_23:{m:41.9,sd:15.2},thymus_01:{m:7.5,sd:3.6},thymus_2:{m:6.2,sd:3.6},thymus_3:{m:3.8,sd:3.6},spleen_01:{m:8.1,sd:2.5},spleen_23:{m:6.7,sd:2.5},kidneys_01:{m:25.4,sd:6.2},kidneys_23:{m:21.4,sd:6.2},adrenals_01:{m:6.9,sd:2.0},adrenals_23:{m:5.6,sd:2.0}},
  {s:37,brain:{m:340,sd:36},heart:{m:16,sd:3.3},liver_01:{m:142,sd:33},liver_2:{m:100,sd:33},liver_3:{m:71.7,sd:32.7},lungs_01:{m:58.1,sd:16.1},lungs_23:{m:45.1,sd:16.1},thymus_01:{m:8.2,sd:3.9},thymus_2:{m:6.8,sd:3.9},thymus_3:{m:4.2,sd:3.9},spleen_01:{m:9.1,sd:2.7},spleen_23:{m:7.5,sd:2.7},kidneys_01:{m:27.5,sd:6.6},kidneys_23:{m:23.2,sd:6.6},adrenals_01:{m:7.4,sd:2.1},adrenals_23:{m:6.0,sd:2.1}},
  {s:38,brain:{m:366,sd:38},heart:{m:17.2,sd:3.4},liver_01:{m:154,sd:34},liver_2:{m:107,sd:34},liver_3:{m:77.2,sd:34.2},lungs_01:{m:62.2,sd:17},lungs_23:{m:48.5,sd:17},thymus_01:{m:8.9,sd:4.2},thymus_2:{m:7.4,sd:4.2},thymus_3:{m:3.9,sd:4.2},spleen_01:{m:10.1,sd:3.0},spleen_23:{m:8.3,sd:3.0},kidneys_01:{m:29.8,sd:7.1},kidneys_23:{m:25,sd:7.1},adrenals_01:{m:7.8,sd:2.2},adrenals_23:{m:6.5,sd:2.2}},
  {s:39,brain:{m:394,sd:39},heart:{m:18.5,sd:3.6},liver_01:{m:165,sd:36},liver_2:{m:116,sd:36},liver_3:{m:82.8,sd:35.6},lungs_01:{m:66.5,sd:18},lungs_23:{m:52.1,sd:18},thymus_01:{m:9.7,sd:4.6},thymus_2:{m:8.0,sd:4.6},thymus_3:{m:5.0,sd:4.6},spleen_01:{m:11.2,sd:3.2},spleen_23:{m:9.1,sd:3.2},kidneys_01:{m:32.1,sd:7.5},kidneys_23:{m:27,sd:7.5},adrenals_01:{m:8.3,sd:2.3},adrenals_23:{m:6.9,sd:2.3}},
  {s:40,brain:{m:422,sd:41},heart:{m:19.8,sd:3.7},liver_01:{m:177,sd:37},liver_2:{m:124,sd:37},liver_3:{m:88.6,sd:37.1},lungs_01:{m:70.9,sd:18.9},lungs_23:{m:55.7,sd:18.9},thymus_01:{m:10.5,sd:4.9},thymus_2:{m:8.6,sd:4.9},thymus_3:{m:5.4,sd:4.9},spleen_01:{m:12.4,sd:3.4},spleen_23:{m:9.9,sd:3.4},kidneys_01:{m:34.5,sd:8.0},kidneys_23:{m:29,sd:8.0},adrenals_01:{m:8.8,sd:2.4},adrenals_23:{m:7.4,sd:2.4}},
  {s:41,brain:{m:451,sd:42},heart:{m:21.2,sd:3.9},liver_01:{m:190,sd:39},liver_2:{m:133,sd:39},liver_3:{m:94.6,sd:38.5},lungs_01:{m:75.4,sd:19.8},lungs_23:{m:59.5,sd:19.8},thymus_01:{m:11.3,sd:5.3},thymus_2:{m:9.3,sd:5.3},thymus_3:{m:5.8,sd:5.3},spleen_01:{m:13.5,sd:3.7},spleen_23:{m:10.8,sd:3.7},kidneys_01:{m:37.1,sd:8.5},kidneys_23:{m:31,sd:8.5},adrenals_01:{m:9.3,sd:2.6},adrenals_23:{m:7.8,sd:2.6}},
  {s:42,brain:{m:481,sd:44},heart:{m:22.7,sd:4.0},liver_01:{m:203,sd:41},liver_2:{m:142,sd:41},liver_3:{m:100,sd:40},lungs_01:{m:80.1,sd:20.8},lungs_23:{m:63.4,sd:20.8},thymus_01:{m:12.2,sd:5.7},thymus_2:{m:10,sd:5.7},thymus_3:{m:6.3,sd:5.7},spleen_01:{m:14.8,sd:3.9},spleen_23:{m:11.8,sd:3.9},kidneys_01:{m:39.8,sd:9.0},kidneys_23:{m:33.2,sd:9.0},adrenals_01:{m:9.8,sd:2.7},adrenals_23:{m:8.3,sd:2.7}},
  {s:43,brain:{m:512,sd:46},heart:{m:24.2,sd:4.2},liver_01:{m:216,sd:43},liver_2:{m:152,sd:43},liver_3:{m:106,sd:42},lungs_01:{m:84.9,sd:21.8},lungs_23:{m:67.5,sd:21.8},thymus_01:{m:13.2,sd:6.0},thymus_2:{m:10.8,sd:6.0},thymus_3:{m:6.8,sd:6.0},spleen_01:{m:16.1,sd:4.2},spleen_23:{m:12.8,sd:4.2},kidneys_01:{m:42.6,sd:9.5},kidneys_23:{m:35.6,sd:9.5},adrenals_01:{m:10.4,sd:2.8},adrenals_23:{m:8.8,sd:2.8}}
];

// ═══ MULLER-BROCHUT 2018 — Masses d'organes (12-20 SA) ═══
// All in grams
var MB_ORG = {
  12:{Brain:{m:3.6,sd:2.03},Thymus:{m:0.10,sd:0.06},Heart:{m:0.15,sd:0.09},Lungs:{m:0.49,sd:0.24},Liver:{m:1.15,sd:0.43},Spleen:{m:0.05,sd:0.07},Kidneys:{m:0.24,sd:0.13},Adrenals:{m:0.10,sd:0.06}},
  13:{Brain:{m:5.26,sd:1.14},Thymus:{m:0.14,sd:0.06},Heart:{m:0.21,sd:0.06},Lungs:{m:0.89,sd:0.29},Liver:{m:1.49,sd:0.30},Spleen:{m:0.34,sd:0.07},Kidneys:{m:0.61,sd:0.21},Adrenals:{m:0.12,sd:0.05}},
  14:{Brain:{m:7.96,sd:2.03},Thymus:{m:0.11,sd:0.05},Heart:{m:0.33,sd:0.12},Lungs:{m:1.52,sd:0.43},Liver:{m:2.36,sd:0.52},Spleen:{m:0.55,sd:0.04},Kidneys:{m:0.63,sd:0.13},Adrenals:{m:0.25,sd:0.08}},
  15:{Brain:{m:11.33,sd:2.21},Thymus:{m:0.17,sd:0.06},Heart:{m:0.46,sd:0.15},Lungs:{m:2.34,sd:0.58},Liver:{m:3.37,sd:0.66},Spleen:{m:0.65,sd:0.15},Kidneys:{m:1.05,sd:0.25},Adrenals:{m:0.41,sd:0.33}},
  16:{Brain:{m:15.48,sd:3.19},Thymus:{m:0.19,sd:0.05},Heart:{m:0.64,sd:0.12},Lungs:{m:3.04,sd:0.55},Liver:{m:4.63,sd:0.78},Spleen:{m:0.79,sd:0.06},Kidneys:{m:1.17,sd:0.33},Adrenals:{m:0.47,sd:0.36}},
  17:{Brain:{m:20.13,sd:2.62},Thymus:{m:0.22,sd:0.13},Heart:{m:0.80,sd:0.19},Lungs:{m:3.93,sd:0.61},Liver:{m:6.07,sd:1.07},Spleen:{m:0.96,sd:0.14},Kidneys:{m:1.50,sd:0.35},Adrenals:{m:0.61,sd:0.28}},
  18:{Brain:{m:26.26,sd:4.48},Thymus:{m:0.24,sd:0.06},Heart:{m:1.14,sd:0.36},Lungs:{m:4.89,sd:0.76},Liver:{m:7.92,sd:1.21},Spleen:{m:1.21,sd:0.15},Kidneys:{m:1.76,sd:0.51},Adrenals:{m:0.90,sd:0.23}},
  19:{Brain:{m:34.58,sd:5.02},Thymus:{m:0.29,sd:0.09},Heart:{m:1.65,sd:0.43},Lungs:{m:6.09,sd:0.25},Liver:{m:10.77,sd:1.45},Spleen:{m:0.90,sd:0.24},Kidneys:{m:2.13,sd:0.41},Adrenals:{m:1.05,sd:0.24}},
  20:{Brain:{m:46.0,sd:0.57},Thymus:{m:0.26,sd:0.14},Heart:{m:1.99,sd:0.18},Lungs:{m:6.64,sd:1.15},Liver:{m:12.76,sd:1.23},Spleen:{m:0.55,sd:0.26},Kidneys:{m:2.63,sd:0.63},Adrenals:{m:1.27,sd:0.32}}
};

// ═══ GENEST — Critères de rétention in utero ═══
var GENEST = [
  {id:0,t:"Toute desquamation",time:"≥ 3h",q:"inter"},
  {id:1,t:"Desquamation ≥ 1 cm",time:"≥ 6h",q:"bon"},
  {id:2,t:"Décoloration cordon (brun/rouge)",time:"≥ 6h",q:"bon"},
  {id:3,t:"Desquamation face, dos ou abdomen",time:"≥ 12h",q:"bon"},
  {id:4,t:"Desquamation ≥ 5% surface",time:"≥ 18h",q:"bon"},
  {id:5,t:"Desquamation ≥ 2 zones / 11",time:"≥ 18h",q:"bon"},
  {id:6,t:"Coloration cutanée brune/ocre",time:"≥ 24h",q:"bon"},
  {id:7,t:"Desquamation modérée ou sévère",time:"≥ 24h",q:"bon"},
  {id:8,t:"Compression crânienne",time:"≥ 36h",q:"mauv"},
  {id:9,t:"Desquamation > 10% surface",time:"≥ 48h",q:"mauv"},
  {id:10,t:"Desquamation > 75% surface",time:"≥ 72h",q:"mauv"},
  {id:11,t:"Bouche largement ouverte",time:"≥ 1 sem.",q:"mauv"},
  {id:12,t:"Momification",time:"≥ 2 sem.",q:"bon"},
  {id:13,t:"Coloration cutanée ocre",time:"≥ 4 sem.",q:"inter"}
];
var TIME_ORDER = ["≥ 3h","≥ 6h","≥ 12h","≥ 18h","≥ 24h","≥ 36h","≥ 48h","≥ 72h","≥ 1 sem.","≥ 2 sem.","≥ 4 sem."];

// ═══ BIOMETRY FIELD DEFINITIONS ═══
var CAL_FIELDS = [
  {id:'pied',l:'Longueur pied',gc:'pied',ma:'F',mb:'Foot',mbd:10},
  {id:'bip',l:'BIP',mb:'BPD',mbd:10},
  {id:'fo',l:'FO (Fronto-Occ.)',mb:'FOD',mbd:10},
  {id:'dici',l:'DICI'},{id:'dice',l:'DICE'},
  {id:'fpg',l:'FPG (Fente palp. G)'},{id:'fpd',l:'FPD (Fente palp. D)'},
  {id:'dim',l:'DIM (Intermam.)'},{id:'sternum',l:'Hauteur sternum'},
  {id:'main',l:'Hauteur main',mb:'Hand',mbd:10}
];
var TAPE_FIELDS = [
  {id:'vt',l:'VT (Vertex-Talon)',gc:'VT',ma:'H',mad:10,mb:'CFL',mbd:10},
  {id:'vc',l:'VC (Vertex-Coccyx)',gc:'VC',ma:'C',mad:10,mb:'CRL',mbd:10},
  {id:'pc',l:'PC (Périm. crânien)',gc:'PC',ma:'D',mad:10,mb:'HC',mbd:10},
  {id:'pt',l:'PT (Périm. thorac.)',mb:'TC',mbd:10},
  {id:'pa',l:'PA (Périm. abdom.)',mb:'AC',mbd:10}
];

// ═══ MORPHOLOGY DEFINITIONS ═══
var MORPHO = [
  {id:'aspect_general',l:'Aspect général',details:[]},
  {id:'symetrie',l:'Symétrie',details:[]},
  {id:'proportions',l:'Proportions',details:[]},
  {id:'teguments',l:'Téguments',details:['Méconium','Pâleur','Ictère','Cyanose','Œdème','Congestion','Hémorragie','Pétéchies']},
  {id:'pilosite',l:'Pilosité',details:[]},
  {id:'cheveux',l:'Implant. cheveux',details:[]},
  {id:'ongles',l:'Ongles',details:[]},
  {id:'crane',l:'Forme crâne',details:['Dolichocéphalie','Brachycéphalie','Scaphocéphalie','Turricéphalie','Plagiocéphalie']},
  {id:'fontanelles',l:'Fontanelles / Sutures',details:[]},
  {id:'yeux',l:'Yeux',details:['Hypertélorisme','Hypotélorisme','Microphtalmie','Anophtalmie','Épicanthus']},
  {id:'nez',l:'Nez',details:[]},
  {id:'bouche',l:'Bouche / Palais',details:['Fente labiale','Fente palatine','Microstomie','Rétrognathie','Micrognathie']},
  {id:'oreilles',l:'Oreilles',details:['Implant. basse','Rotation postér.','Microtie','Anotie']},
  {id:'cou',l:'Cou',details:['Pterygium colli','Cou court','Hygroma']},
  {id:'thorax',l:'Thorax',details:['Étroit','En tonneau']},
  {id:'abdomen',l:'Abdomen',details:['Omphalocèle','Laparoschisis','Distendu','Prune belly']},
  {id:'dos',l:'Dos / Rachis',details:['Spina bifida','Scoliose','Fossette sacrale']},
  {id:'oge',l:'OGE',details:['Ambigus','Hypospadias','Cryptorchidie']},
  {id:'anus',l:'Anus',ln:'Perméable',la:'Imperforé'},
  {id:'membres_sup',l:'Membres sup.',details:['Raccourcissement','Agénésie','Incurvation']},
  {id:'membres_inf',l:'Membres inf.',details:['Raccourcissement','Agénésie','Pied bot']},
  {id:'mains',l:'Mains',details:['Polydact. préax.','Polydact. postax.','Syndactylie','Clinodactylie','PPTU','Hockey stick']},
  {id:'pieds_morpho',l:'Pieds',details:['Polydact. préax.','Polydact. postax.','Syndactylie','Rocker-bottom','Sandal gap']},
  {id:'cordon',l:'Cordon',details:['Artère unique','Nœud vrai','Circulaire','Grêle']}
];

// ═══ LOOKUP HELPERS ═══
function getGCKey(sa) {
  if (sa < 13 || sa > 42) return null;
  var keys = Object.keys(GC);
  for (var i = 0; i < keys.length; i++) {
    var p = keys[i].split('-');
    if (sa >= parseInt(p[0]) && sa <= parseInt(p[1])) return keys[i];
  }
  return null;
}
function getMA(sa) {
  for (var i = 0; i < MA.length; i++) { if (MA[i].s === sa) return MA[i]; }
  return null;
}
function getMB(sa) { return (sa >= 12 && sa <= 20) ? MB_BIO[sa] : null; }
function getMAOrg(sa) {
  for (var i = 0; i < MA_ORG.length; i++) { if (MA_ORG[i].s === sa) return MA_ORG[i]; }
  return null;
}
function getMBOrg(sa) { return (sa >= 12 && sa <= 20) ? MB_ORG[sa] : null; }
function getMarounGrade(score) { if (score <= 1) return '01'; if (score === 2) return '2'; return '3'; }
function getMarounGrade23(score) { if (score <= 1) return '01'; return '23'; }

// ═══ GUIHARD-COSTA 2002 — Masses d'organes (bi-hebdomadaire, g) ═══
// Keys: thymus, coeur, poumons, foie, spleen, pancreas, surrenales, reins
var GC_ORG = {
  "13-14":{thymus:{m:0.09,sd:0.07},coeur:{m:0.24,sd:0.13},poumons:{m:1.26,sd:0.25},foie:{m:3.09,sd:0.27},spleen:{m:0.06,sd:0.04},pancreas:{m:0.09,sd:0.01},surrenales:{m:0.29,sd:0.06},reins:{m:0.41,sd:0.11}},
  "15-16":{thymus:{m:0.17,sd:0.12},coeur:{m:0.82,sd:0.23},poumons:{m:2.99,sd:0.54},foie:{m:5.81,sd:1.71},spleen:{m:0.12,sd:0.08},pancreas:{m:0.28,sd:0.08},surrenales:{m:0.56,sd:0.10},reins:{m:0.71,sd:0.18}},
  "17-18":{thymus:{m:0.31,sd:0.19},coeur:{m:1.44,sd:0.37},poumons:{m:5.09,sd:0.91},foie:{m:9.39,sd:3.33},spleen:{m:0.23,sd:0.13},pancreas:{m:0.42,sd:0.16},surrenales:{m:0.91,sd:0.16},reins:{m:1.38,sd:0.27}},
  "19-20":{thymus:{m:0.53,sd:0.3},coeur:{m:2.21,sd:0.56},poumons:{m:7.68,sd:1.34},foie:{m:14.33,sd:5.15},spleen:{m:0.38,sd:0.2},pancreas:{m:0.57,sd:0.24},surrenales:{m:1.32,sd:0.23},reins:{m:2.41,sd:0.38}},
  "21-22":{thymus:{m:0.87,sd:0.45},coeur:{m:3.23,sd:0.79},poumons:{m:10.84,sd:1.84},foie:{m:21,sd:7.15},spleen:{m:0.62,sd:0.29},pancreas:{m:0.78,sd:0.34},surrenales:{m:1.79,sd:0.32},reins:{m:3.84,sd:0.53}},
  "23-24":{thymus:{m:1.35,sd:0.64},coeur:{m:4.55,sd:1.07},poumons:{m:14.65,sd:2.39},foie:{m:29.63,sd:9.35},spleen:{m:0.96,sd:0.42},pancreas:{m:1.08,sd:0.45},surrenales:{m:2.33,sd:0.41},reins:{m:5.64,sd:0.70}},
  "25-26":{thymus:{m:2.01,sd:0.89},coeur:{m:6.21,sd:1.39},poumons:{m:19.09,sd:2.98},foie:{m:40.27,sd:11.75},spleen:{m:1.44,sd:0.59},pancreas:{m:1.47,sd:0.57},surrenales:{m:2.92,sd:0.51},reins:{m:7.78,sd:0.90}},
  "27-28":{thymus:{m:2.92,sd:1.21},coeur:{m:8.2,sd:1.76},poumons:{m:24.15,sd:3.61},foie:{m:52.89,sd:14.33},spleen:{m:2.09,sd:0.8},pancreas:{m:1.98,sd:0.7},surrenales:{m:3.57,sd:0.61},reins:{m:10.22,sd:1.12}},
  "29-30":{thymus:{m:4.14,sd:1.61},coeur:{m:10.48,sd:2.17},poumons:{m:29.79,sd:4.27},foie:{m:67.29,sd:17.1},spleen:{m:2.95,sd:1.06},pancreas:{m:2.58,sd:0.84},surrenales:{m:4.3,sd:0.72},reins:{m:12.9,sd:1.37}},
  "31-32":{thymus:{m:5.72,sd:2.1},coeur:{m:12.98,sd:2.63},poumons:{m:35.9,sd:4.94},foie:{m:83.1,sd:20.07},spleen:{m:4.08,sd:1.39},pancreas:{m:3.26,sd:0.98},surrenales:{m:5.08,sd:0.82},reins:{m:15.73,sd:1.65}},
  "33-34":{thymus:{m:7.75,sd:2.7},coeur:{m:15.6,sd:3.14},poumons:{m:42.36,sd:5.62},foie:{m:99.87,sd:23.23},spleen:{m:5.53,sd:1.78},pancreas:{m:3.97,sd:1.14},surrenales:{m:5.93,sd:0.92},reins:{m:18.62,sd:1.96}},
  "35-36":{thymus:{m:10.33,sd:3.42},coeur:{m:18.21,sd:3.69},poumons:{m:48.98,sd:6.30},foie:{m:116.97,sd:26.58},spleen:{m:7.35,sd:2.25},pancreas:{m:4.66,sd:1.31},surrenales:{m:6.83,sd:1.01},reins:{m:21.46,sd:2.29}},
  "37-38":{thymus:{m:13.54,sd:4.27},coeur:{m:20.63,sd:4.28},poumons:{m:55.59,sd:6.98},foie:{m:133.64,sd:30.12},spleen:{m:9.63,sd:2.82},pancreas:{m:5.26,sd:1.49},surrenales:{m:7.79,sd:1.09},reins:{m:24.12,sd:2.65}},
  "39-40":{thymus:{m:17.5,sd:5.27},coeur:{m:22.68,sd:4.92},poumons:{m:61.94,sd:7.64},foie:{m:148.97,sd:33.85},spleen:{m:12.43,sd:3.48},pancreas:{m:5.71,sd:1.67},surrenales:{m:8.83,sd:1.17},reins:{m:26.45,sd:3.04}},
  "41-42":{thymus:{m:22.34,sd:6.44},coeur:{m:24.49,sd:5.58},poumons:{m:67.6,sd:8.28},foie:{m:161.94,sd:37.78},spleen:{m:15.85,sd:4.25},pancreas:{m:5.9,sd:1.87},surrenales:{m:9.92,sd:1.22},reins:{m:28.28,sd:3.45}}
};
function getGCOrg(sa) { return (sa >= 13 && sa <= 42) ? GC_ORG[getGCKey(sa)] : null; }
