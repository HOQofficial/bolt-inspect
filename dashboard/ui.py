"""화면 공용 부품: 큰 판정 배너, 상태 배지, 게이지, 스펙트럼."""
import plotly.graph_objects as go
import streamlit as st

# 밝은/어두운 테마 모두에서 읽히는 진한 색 + 흰 글씨
# 폰 앱(web/app/style.css)과 같은 색: 주황 포인트 + 초록(정상) / 노랑(재측정) / 빨강(이상)
ACCENT = "#ff5900"
COLOR = {"OK": "#1f9d55", "CHECK": "#e6b800", "NG": "#e0413a", None: "#64748b"}
SOFT = {"OK": "#d9f2e4", "CHECK": "#ffebc2", "NG": "#ffd9d6", None: "#eceef7"}
INK = {"OK": "#14633f", "CHECK": "#7a5200", "NG": "#8e2019", None: "#3a4056"}   # 연한 칸 위의 글자색
PINK, PINK_SOFT, PINK_INK = "#ff3d81", "#ff9cc2", "#e11d63"       # Peak 점·말풍선
GRAD = {"OK": "linear-gradient(135deg,#1f9d55,#3fc27a)", "CHECK": "linear-gradient(135deg,#ffd93d,#ffec8a)",
        "NG": "linear-gradient(135deg,#e0413a,#f37a70)", None: "linear-gradient(135deg,#64748b,#94a3b8)"}
ON_GRAD = {"OK": "#fff", "CHECK": "#4a3b00", "NG": "#fff", None: "#fff"}
BAND = "#cfe8d9"          # 정상 범위 칸 (연한 세이지 그린)
KO = {"OK": "정상", "CHECK": "재측정 필요", "NG": "체결 이상 의심", None: "미검사"}
KO_SHORT = {"OK": "정상", "CHECK": "재측정", "NG": "이상"}
ICON = {"OK": "●", "CHECK": "▲", "NG": "■", None: "○"}


RIBBON_D = "M1068 -176 L1074 -167 L1079 -158 L1084 -149 L1089 -140 L1094 -131 L1098 -121 L1102 -112 L1106 -103 L1110 -94 L1113 -84 L1117 -75 L1120 -66 L1123 -57 L1125 -47 L1127 -38 L1129 -29 L1131 -20 L1133 -11 L1134 -2 L1135 6 L1136 15 L1137 23 L1138 32 L1138 40 L1138 48 L1138 56 L1137 64 L1137 71 L1136 78 L1135 86 L1133 92 L1132 99 L1130 106 L1129 112 L1127 118 L1124 123 L1122 129 L1120 134 L1117 138 L1114 143 L1112 147 L1109 151 L1106 155 L1103 158 L1099 161 L1096 163 L1093 166 L1089 168 L1086 169 L1083 171 L1079 172 L1076 172 L1072 173 L1069 172 L1066 172 L1062 171 L1059 170 L1056 169 L1053 167 L1050 165 L1047 163 L1044 161 L1041 158 L1038 154 L1036 151 L1034 147 L1032 143 L1030 139 L1028 135 L1026 130 L1025 125 L1024 120 L1023 115 L1022 110 L1021 104 L1021 98 L1021 93 L1021 87 L1022 81 L1023 75 L1024 68 L1025 62 L1026 56 L1028 50 L1030 44 L1033 37 L1035 31 L1038 25 L1041 19 L1045 13 L1048 7 L1052 2 L1056 -4 L1061 -9 L1065 -14 L1070 -19 L1076 -24 L1081 -28 L1087 -33 L1092 -36 L1098 -40 L1105 -44 L1111 -47 L1118 -49 L1125 -52 L1131 -54 L1138 -55 L1146 -57 L1153 -57 L1160 -58 L1168 -58 L1175 -58 L1183 -57 L1191 -56 L1198 -54 L1206 -52 L1214 -49 L1222 -46 L1229 -43 L1237 -39 L1245 -34 L1252 -30 L1260 -24 L1267 -18 L1274 -12 L1281 -5 L1288 2 L1295 9 L1301 17 L1308 26 L1314 35 L1320 44 L1325 54 L1331 64 L1336 75 L1340 85 L1345 97 L1349 108 L1353 120 L1356 133 L1360 145 L1362 158 L1365 171 L1367 185 L1369 198 L1370 212 L1371 226 L1371 240 L1371 255 L1371 269 L1370 284 L1369 299 L1367 314 L1365 329 L1363 344 L1360 359 L1356 374 L1353 389 L1348 404 L1344 418 L1338 433 L1333 448 L1327 462 L1321 477 L1314 491 L1306 505 L1299 519 L1291 533 L1283 546 L1274 559 L1265 572 L1255 584 L1245 597 L1235 609 L1225 620 L1214 631 L1203 642 L1192 653 L1180 663 L1168 672 L1156 681 L1144 690 L1132 699 L1119 707 L1106 714 L1093 721 L1080 728 L1067 734 L1054 739 L1040 744 L1027 749 L1013 753 L1000 757 L986 760 L973 763 L959 765 L946 767 L932 769 L919 770 L905 770 L892 770 L879 770 L866 769 L853 768 L840 766 L828 764 L816 762 L804 759 L792 756 L780 753 L768 749 L757 745 L746 740 L735 736 L725 731 L715 726 L705 720 L695 715 L686 709 L677 703 L669 697 L660 691 L652 684 L645 678 L637 671 L630 665 L623 658 L617 651 L611 645 L605 638 L600 631 L595 625 L590 618 L586 612 L582 605 L578 599 L574 593 L571 587 L568 581 L566 576 L563 570 L561 565 L560 560 L558 555 L557 551 L556 547 L555 543 L554 539 L554 536 L554 532 L554 530 L554 527 L554 525 L555 523 L556 522 L556 521 L557 520 L558 519 L559 519 L560 520 L562 520 L563 521 L564 523 L566 524 L567 526 L568 529 L570 532 L571 535 L573 538 L574 542 L575 546 L576 551 L578 555 L579 560 L580 566 L581 572 L581 578 L582 584 L583 590 L583 597 L584 604 L584 612 L584 619 L584 627 L583 635 L583 643 L582 652 L582 660 L581 669 L580 678 L578 687 L577 696 L575 705 L573 715 L571 724 L569 734 L566 743 L564 753 L561 763 L558 772 L555 782 L551 792 L548 802 L544 812 L540 821 L536 831 L532 841 L527 850 L523 860 L518 870 L513 879 L508 888 L503 898 L498 907 L492 916 L487 925 L481 933 L475 942 L469 950 L463 959 L457 967 L451 975 L444 983 L438 991 L432 998 L425 1005 L419 1013 L412 1019 L405 1026 L399 1033 L392 1039 L385 1045 L378 1052 L372 1057 L365 1063 L358 1068 L351 1074 L345 1079 L338 1084 L331 1088 L325 1093 L318 1097 L312 1101 L305 1105 L299 1109 L293 1112 L286 1116 L280 1119 L274 1122 L268 1125 L262 1127 L256 1130 L251 1132 L245 1134 L240 1136 L234 1138 L229 1140 L224 1142 L219 1143 L214 1144 L209 1146 L205 1147 L200 1148 L196 1148 L192 1149 L188 1150 L184 1150 L180 1151 L177 1151 L173 1151 L170 1151 L167 1151 L164 1151 L161 1151 L158 1151 L156 1151 L154 1151 L152 1150 L150 1150 L148 1149 L146 1149 L145 1148 L144 1148 L142 1147 L142 1147 L141 1146 L140 1145 L140 1145 L140 1144 L140 1143 L140 1143 L140 1142 L140 1141 L141 1141 L142 1140 L143 1139 L144 1139 L145 1138 L147 1138 L149 1137 L151 1137 L153 1137 L155 1136 L157 1136 L160 1136 L162 1136 L165 1136 L168 1136 L172 1136 L175 1136 L178 1137 L182 1137 L186 1138 L190 1138 L194 1139 L198 1140 L203 1141 L207 1142 L212 1143 L217 1145 L222 1146 L227 1148 L232 1150 L237 1152 L243 1154 L248 1156 L254 1159 L260 1161 L266 1164 L272 1167 L278 1170 L284 1174 L290 1177 L296 1181 L303 1185 L309 1189 L316 1193 L322 1198 L329 1203 L335 1207 L342 1213 L348 1218 L355 1223 L362 1229 L368 1235 L375 1241 L382 1247 L388 1254 L395 1261 L401 1268 L408 1275 L414 1282 L421 1290 L427 1297 L433 1305 L440 1313 L446 1321 L452 1330 L458 1338 L463 1347 L469 1356 L475 1365 L480 1374 L485 1383 L490 1392 L495 1402 L500 1411 L505 1421 L510 1431 L514 1440 L518 1450 L522 1460 L526 1470 L530 1480 L533 1490 L537 1500 L540 1510 L543 1520 L546 1530 L548 1540 L550 1550 L553 1559 L555 1569 L556 1579 L558 1588 L559 1598 L561 1607 L562 1616 L563 1625 L563 1634 L564 1643 L564 1651 L564 1659 L564 1667 L564 1675 L564 1683 L563 1690 L563 1697 L562 1704 L561 1711 L560 1717 L559 1723 L558 1728 L556 1734 L555 1739 L554 1744 L552 1748 L551 1752 L549 1756 L547 1759 L546 1762 L544 1765 L543 1767 L541 1769 L539 1770 L538 1772 L536 1772 L535 1773 L534 1773 L532 1773 L531 1772 L530 1771 L529 1770 L529 1768 L528 1766 L528 1764 L527 1761 L527 1758 L527 1754 L528 1751 L528 1747 L529 1743 L530 1738 L531 1734 L533 1729 L535 1723 L537 1718 L539 1712 L542 1706 L545 1700 L548 1694 L552 1688 L556 1681 L560 1675 L564 1668 L569 1662 L574 1655 L580 1648 L586 1641 L592 1634 L599 1627 L605 1621 L613 1614 L620 1607 L628 1601 L636 1594 L645 1588 L654 1582 L663 1576 L673 1570 L682 1564 L692 1559 L703 1554 L714 1549 L725 1544 L736 1540 L747 1536 L759 1532 L771 1529 L783 1526 L795 1523 L808 1521 L821 1519 L834 1517 L847 1516 L860 1516 L873 1515 L887 1515 L900 1516 L914 1517 L928 1519 L941 1521 L955 1523 L969 1526 L983 1530 L996 1534 L1010 1538 L1024 1543 L1037 1548 L1051 1554 L1064 1560 L1077 1567 L1090 1574 L1103 1582 L1116 1590 L1129 1599 L1141 1607 L1153 1617 L1165 1627 L1177 1637 L1188 1648 L1199 1659 L1210 1670 L1221 1682 L1231 1694 L1241 1706 L1250 1719 L1259 1732 L1268 1745 L1277 1758 L1285 1772 L1292 1786 L1300 1800 L1306 1814 L1313 1829 L1319 1843 L1325 1858 L1330 1873 L1334 1888 L1339 1903 L1343 1918 L1346 1933 L1349 1948 L1352 1963 L1354 1977 L1356 1992 L1357 2007 L1358 2022 L1358 2036 L1358 2050 L1358 2065 L1357 2079 L1356 2092 L1354 2106 L1352 2119 L1350 2132 L1347 2145 L1344 2157 L1341 2169 L1337 2181 L1333 2193 L1329 2204 L1324 2214 L1319 2225 L1314 2235 L1309 2244 L1303 2253 L1297 2262 L1291 2270 L1285 2278 L1278 2286 L1272 2293 L1265 2299 L1258 2305 L1251 2311 L1244 2316 L1237 2321 L1229 2325 L1222 2329 L1215 2332 L1207 2335 L1200 2337 L1193 2339 L1185 2341 L1178 2342 L1171 2342 L1163 2343 L1156 2343 L1149 2342 L1142 2341 L1136 2340 L1129 2338 L1122 2336 L1116 2333 L1110 2331 L1104 2328 L1098 2324 L1092 2321 L1087 2317 L1082 2312 L1077 2308 L1072 2303 L1068 2298 L1063 2293 L1059 2288 L1056 2283 L1052 2277 L1049 2271 L1046 2266 L1043 2260 L1041 2254 L1038 2248 L1036 2242 L1035 2236 L1033 2230 L1032 2224 L1031 2218 L1031 2212 L1030 2206 L1030 2200 L1030 2194 L1030 2189 L1031 2183 L1032 2178 L1033 2173 L1034 2168 L1036 2163 L1037 2158 L1039 2154 L1041 2150 L1043 2146 L1046 2142 L1048 2139 L1051 2135 L1053 2133 L1056 2130 L1059 2128 L1062 2126 L1066 2124 L1069 2122 L1072 2121 L1076 2120 L1079 2120 L1083 2120 L1086 2120 L1090 2120 L1093 2121 L1097 2122 L1100 2124 L1104 2125 L1107 2128 L1110 2130 L1114 2133 L1117 2136 L1120 2139 L1123 2143 L1126 2147 L1129 2151 L1132 2156 L1134 2160 L1137 2166 L1139 2171 L1141 2177 L1143 2183 L1145 2189 L1146 2195 L1148 2202 L1149 2209 L1150 2216 L1151 2223 L1152 2230 L1152 2238 L1152 2246 L1152 2254 L1152 2262 L1152 2270 L1151 2278 L1150 2287 L1149 2296 L1148 2304 L1146 2313 L1144 2322 L1142 2331 L1140 2340 L1137 2349 L1135 2358 L1132 2367 L1129 2376 L1125 2385 L1121 2394 L1118 2403 L1114 2413 L1109 2422 L1105 2431 L1100 2439 L1095 2448 L1090 2457 L1085 2466 L1079 2475 L1073 2483 L1067 2492 L1061 2500 L1055 2508 L1049 2517 L1042 2525 L1036 2532 L1029 2540 L1022 2548 L1014 2555 L1007 2563 L1000 2570 L992 2577 L985 2584 L977 2591 L969 2598 L961 2604 L953 2610 L945 2617 L937 2623 L928 2628 L920 2634 L911 2639 L903 2645 L894 2650 L886 2655 L877 2660 L869 2664 L860 2669 L851 2673 L842 2677 L834 2681 L825 2685 L816 2689 L807 2692 L799 2696 L790 2699 L781 2702 L772 2705 L764 2708 L755 2710 L746 2713 L738 2715 L729 2717 L721 2719 L712 2721 L704 2723 L695 2724 L687 2726 L679 2727 L671 2728 L663 2729 L655 2730 L647 2731 L639 2732 L631 2733 L623 2733 L616 2734 L608 2734 L601 2734 L594 2734 L586 2734 L579 2734 L572 2734 L565 2734 L558 2734 L552 2734 L545 2733 L539 2733 L532 2732 L526 2732 L520 2731 L514 2731 L508 2730 L503 2729 L497 2728 L492 2728 L487 2727 L481 2726 L476 2725 L472 2724 L467 2724 L462 2723 L458 2722 L454 2721 L449 2720 L446 2719 L442 2719 L438 2718 L435 2717 L431 2717 L428 2716 L425 2716 L422 2715 L419 2715 L417 2715 L414 2714 L412 2714 L410 2714 L408 2714 L406 2714 L404 2715 L403 2715 L401 2716 L400 2716 L399 2717 L398 2718 L397 2719 L396 2720 L396 2722 L395 2723 L395 2725 L395 2727 L394 2729 L394 2731 L394 2734 L394 2737 L395 2739 L395 2743 L395 2746 L396 2749 L396 2753 L397 2757 L398 2761 L398 2766 L399 2770 L400 2775 L400 2780 L401 2786 L402 2791 L403 2797 L404 2803 L404 2809 L405 2816 L406 2823 L407 2829 L407 2837 L408 2844 L409 2852 L409 2859 L410 2868 L410 2876 L410 2884 L410 2893 L410 2902 L410 2911 L410 2920 L410 2929 L409 2939 L409 2948 L408 2958 L407 2968 L406 2978 L405 2989 L404 2999 L402 3009 L401 3020 L399 3030 L397 3041 L395 3052 L392 3062 L390 3073 L387 3084 L384 3095 L381 3105 L377 3116 L374 3127 L370 3137 L366 3148 L362 3158 L357 3168 L353 3179 L348 3189 L343 3199 L338 3208 L333 3218 L327 3228 L322 3237 L316 3246 L310 3255 L304 3263 L298 3272 L291 3280 L285 3287 L278 3295 L271 3302 L264 3309 L257 3316 L250 3322 L243 3328 L236 3334 L229 3339 L222 3344 L214 3348 L207 3352 L200 3356 L193 3360 L185 3363 L178 3365 L171 3367 L164 3369 L157 3371 L150 3372 L143 3373 L137 3373 L130 3373 L124 3372 L117 3371 L111 3370 L105 3368 L100 3366 L94 3364 L89 3361 L84 3358 L79 3355 L75 3351 L71 3347 L67 3343 L63 3338 L60 3333 L57 3328 L54 3322 L52 3317 L50 3311 L48 3305 L47 3298 L46 3292 L46 3285 L46 3278 L46 3271 L47 3264 L48 3257 L50 3250 L51 3242 L54 3235 L57 3228 L60 3220 L63 3213 L67 3206 L72 3198 L77 3191 L82 3184 L88 3177 L94 3170 L100 3164 L107 3157 L114 3151 L122 3145 L130 3139 L138 3134 L147 3129 L156 3124 L165 3119 L175 3115 L185 3111 L195 3107 L206 3104 L217 3101 L228 3098 L239 3096 L251 3095 L263 3093 L275 3092 L287 3092 L300 3092 L312 3093 L325 3094 L338 3095 L351 3097 L364 3099 L377 3102 L390 3106 L403 3110 L416 3114 L430 3119 L443 3124 L456 3130 L469 3136 L482 3143 L495 3150 L508 3158 L521 3166 L534 3174 L546 3183 L559 3193 L571 3203 L583 3213 L594 3223 L606 3234 L617 3246 L628 3257 L639 3269 L650 3282 L660 3294 L670 3307 L680 3320 L689 3334 L698 3347 L707 3361 L716 3375 L724 3390 L731 3404 L739 3418 L746 3433 L753 3448 L759 3462 L765 3477 L770 3492 L776 3507 L781 3522 L785 3536 L789 3551 L793 3566 L796 3580 L799 3595 L802 3609 L805 3623 L807 3637 L808 3651 L810 3664 L811 3678 L812 3691 L812 3703 L812 3716 L812 3728 L812 3740 L811 3752 L811 3763 L809 3774 L808 3784 L807 3794 L805 3804 L803 3814 L801 3823 L799 3831 L796 3839 L794 3847 L791 3854 L789 3861 L786 3868 L783 3874 L780 3879 L777 3884 L774 3889 L771 3893 L769 3897 L766 3900 L763 3903 L760 3906 L757 3908 L754 3910 L752 3911 L749 3912 L747 3912 L745 3912 L743 3912 L741 3911 L739 3910 L737 3909 L736 3907 L734 3905 L733 3903 L733 3900 L732 3897 L732 3894 L731 3891 L732 3887 L732 3883 L733 3879 L733 3874 L735 3870 L736 3865 L738 3861 L740 3856 L742 3851 L744 3845 L747 3840 L750 3835 L753 3830 L757 3824 L761 3819 L765 3814 L769 3808 L774 3803 L779 3798 L784 3792 L790 3787 L795 3782 L801 3777 L808 3773 L814 3768 L821 3764 L828 3759 L835 3755 L842 3751 L849 3747 L857 3744 L865 3740 L873 3737 L881 3734 L889 3732 L898 3729 L906 3727 L915 3725 L924 3723 L932 3722 L941 3721 L950 3720 L960 3720 L969 3719 L978 3720 L987 3720 L996 3721 L1005 3722 L1015 3723 L1024 3724 L1033 3726 L1042 3728 L1051 3731 L1060 3733 L1069 3736 L1078 3740 L1087 3743 L1096 3747 L1104 3751 L1113 3755 L1121 3760 L1129 3765 L1138 3770 L1146 3775 L1153 3781 L1161 3786 L1169 3792 L1176 3798 L1183 3805 L1190 3811 L1197 3818 L1203 3825 L1210 3832 L1216 3839 L1222 3847 L1228 3854 L1234 3862 L1239 3870 L1244 3878 L1249 3886 L1254 3894 L1258 3902 L1263 3910 L1267 3918 L1270 3927 L1274 3935 L1278 3943 L1281 3952 L1284 3960 L1286 3969 L1289 3977 L1291 3986 L1293 3994 L1295 4003 L1297 4011 L1298 4019 L1299 4028 L1300 4036 L1301 4044 L1302 4053 L1302 4061 L1303 4069 L1303 4077 L1302 4085 L1302 4092 L1302 4100 L1301 4108 L1300 4115 L1299 4123 L1298 4130 L1296 4137 L1295 4144 L1293 4151 L1291 4158 L1289 4165 L1287 4171 L1285 4178 L1283 4184 L1280 4190 L1277 4196 L1275 4202 L1272 4208 L1269 4213 L1266 4219 L1262 4224 L1259 4229 L1256 4234 L1252 4239 L1249 4244 L1245 4249 L1241 4253 L1237 4257 L1233 4261 L1229 4265 L1225 4269 L1221 4273 L1217 4277 L1213 4280 L1209 4283 L1204 4286 L1200 4289 L1195 4292 L1191 4295 L1187 4297 L1182 4300 L1178 4302 L1173 4304 L1168 4306 L1164 4308 L1159 4309 L1155 4311 L1150 4312 L1146 4314 L1141 4315 L1136 4316 L1132 4317 L1127 4318 L1123 4318 L1118 4319 L1114 4319 L1109 4320 L1105 4320 L1100 4320 L1096 4320 L1092 4320 L1087 4320 L1083 4319 L1079 4319 L1075 4319 L1071 4318 L1067 4317 L1063 4317 L1059 4316 L1055 4315 L1052 4314 L1048 4313 L1044 4312 L1041 4311 L1037 4310 L1034 4309 L1031 4308 L1028 4307 L1025 4305 L1022 4304 L1019 4303 L1016 4302 L1013 4301 L1011 4299 L1009 4298 L1006 4297 L1004 4296 L1002 4295 L1000 4294 L998 4293 L996 4292 L994 4291 L993 4290 L991 4290 L990 4289 L989 4289 L987 4288 L986 4288 L985 4288 L985 4288 L984 4288 L983 4288 L982 4289 L982 4289 L981 4290 L981 4291 L981 4292 L981 4294 L980 4295 L980 4297 L980 4299 L980 4301 L980 4304 L980 4306 L980 4309 L980 4312 L981 4315 L981 4319 L981 4323 L981 4327 L981 4331 L981 4336 L981 4341 L981 4346 L981 4351 L981 4357 L981 4363 L981 4369 L980 4375 L980 4382 L980 4389 L979 4396 L978 4404 L977 4412 L976 4420 L975 4428 L974 4436 L973 4445 L971 4454 L969 4463 L967 4472 L965 4482 L963 4492 L960 4502 L957 4512 L954 4522 L951 4533 L948 4543 L944 4554 L940 4565 L936 4576"


def theme_css():
    """폰 앱과 같은 톤: 연보라 바탕 · 둥근 흰 카드 · 알약 버튼. app.py 맨 위에서 한 번 부름 (화면 로직과 무관, 보기만 바꿈)."""
    st.markdown(
        """<style>
        .stApp { background: radial-gradient(520px 360px at 100% 0, rgba(92,225,245,.30), transparent 70%), #ecedfb; }
        [data-testid="stHeader"] { background: transparent; pointer-events:none; }
        [data-testid="stHeader"] > * { pointer-events:auto; }
        [data-testid="stToolbar"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"] { display:none !important; }
        [data-testid="stMain"], [data-testid="stSidebar"] { position:relative; z-index:1; }
        [data-testid="stSidebar"] { z-index:998; }
        [data-testid="stMainBlockContainer"] { padding-top: 5.4rem !important; }
        h1 { font-weight: 300 !important; letter-spacing: -.03em; }
        h1 strong, h2, h3 { letter-spacing: -.02em; }
        h2, h3 { font-weight: 800 !important; }
        [data-testid="stSidebar"] { background: #ffffff; border-radius: 0 28px 28px 0; }
        .stButton > button, .stDownloadButton > button { border-radius: 999px; border: 0; padding: .55rem 1.3rem; background: #ffffff; box-shadow: 0 2px 12px rgba(40,50,120,.10); font-weight: 600; transition: transform .2s ease; }
        .stButton > button:hover { transform: translateY(-2px); }
        .stButton > button[kind="primary"] { background: #ff5900; color: #fff; box-shadow: 0 12px 28px rgba(255,89,0,.34); }
        [data-testid="stMetric"] { background: #ffffff; border-radius: 22px; padding: 14px 18px; box-shadow: 0 10px 34px rgba(40,50,120,.08); }
        [data-testid="stExpander"] { background: #ffffff; border: 0; border-radius: 22px; box-shadow: 0 10px 34px rgba(40,50,120,.07); }
        [class*="st-key-fft_"] [data-testid="stPlotlyChart"] { background: #ffffff; border-radius: 24px; padding: 8px; box-shadow: 0 10px 34px rgba(40,50,120,.07); }
        [class*="st-key-g_"] [data-testid="stPlotlyChart"] { background: #ffffff; border-radius: 18px; }
        [data-testid="stDataFrame"] { border-radius: 18px; overflow: hidden; }
        .rs-hero { margin: 4px 0 18px; }
        .rs-hero small { display:block; font-size:13px; letter-spacing:.14em; color:#5a6076; font-weight:700; margin-bottom:6px; }
        .rs-hero h1 { font-size:64px !important; line-height:1.02; margin:0; padding:0; font-weight:300 !important; letter-spacing:-.045em; color:#0b0f1e; }
        .st-key-btn_add button, .st-key-btn_save button { border-radius:999px !important; height:48px; font-weight:700 !important; border:0 !important; }
        .st-key-btn_add button { background:#ff5a00 !important; color:#fff !important; box-shadow:0 8px 20px -8px rgba(255,90,0,.6); }
        .st-key-btn_save button { background:#0b0f1e !important; color:#fff !important; }
        .st-key-btn_save button:disabled { background:#0b0f1e !important; opacity:.35; }
        @keyframes a-hit { 0%,100%{transform:translateY(0)} 18%{transform:translateY(26px)} 30%{transform:translateY(0)} }
        @keyframes a-arc { 0%,15%{opacity:.15} 22%,60%{opacity:1} 100%{opacity:.15} }
        @keyframes a-eq { 0%,100%{transform:scaleY(.25)} 50%{transform:scaleY(1)} }
        @keyframes a-ring { 0%{stroke-dashoffset:100} 55%,100%{stroke-dashoffset:19} }
        @keyframes a-chk { 0%,40%{stroke-dashoffset:100} 70%,100%{stroke-dashoffset:0} }
        .a-rod { animation:a-hit 1.8s ease-in-out infinite; }
        .a-arc { animation:a-arc 1.8s ease-out infinite; }
        .a-eq { transform-box:fill-box; transform-origin:center; animation:a-eq 1.1s ease-in-out infinite; }
        .a-ring { animation:a-ring 3.2s ease-in-out infinite; }
        .a-chk { stroke-dasharray:100 100; animation:a-chk 3.2s ease-in-out infinite; }
        .st-key-recenthead [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; }
        .st-key-recenthead [data-testid="stColumn"] { min-width:0 !important; }
        .st-key-recenthead [data-testid="stColumn"]:last-child { flex:0 0 auto !important; width:auto !important; }
        .st-key-allbtn { display:flex; justify-content:flex-end; } .st-key-allbtn [data-testid="stElementContainer"], .st-key-allbtn a { margin-left:auto; width:fit-content !important; white-space:nowrap; }
        .st-key-allbtn a { border-radius:999px !important; background:#fff !important; border:1px solid #d9dcef !important; padding:10px 22px !important; width:auto !important; box-shadow:0 6px 18px -10px rgba(40,50,120,.4); }
        .st-key-allbtn a:hover { background:#0b0f1e !important; } .st-key-allbtn a:hover * { color:#fff !important; }
        .st-key-allbtn a p { font-weight:700 !important; font-size:14px !important; margin:0; }
        .rs-rc .pk { display:grid; grid-template-columns:34px 1fr; align-items:center; gap:10px; height:26px; font-size:12px; color:#5a6076; }
        .rs-rc .pk .tr { position:relative; height:6px; border-radius:3px; background:#eceef9; }
        .rs-rc .pk .tr i { position:absolute; top:50%; width:14px; height:14px; margin:-7px 0 0 -7px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 0 1px rgba(0,0,0,.08); }
        .st-key-filter { display:flex; justify-content:flex-end; } .st-key-filter > div { margin-left:auto; }
        .st-key-moreRow [data-testid="stHorizontalBlock"] { justify-content:center; gap:12px; }
        .st-key-moreRow [data-testid="stColumn"] { flex:0 0 130px !important; width:130px !important; min-width:0 !important; }
        .st-key-xlsbtn { display:flex; justify-content:flex-end; } .st-key-xlsbtn > div, .st-key-xlsbtn [data-testid="stElementContainer"] { margin-left:auto; width:fit-content !important; }
        .st-key-xlsbtn button, .st-key-moreRow button { border-radius:999px !important; background:#fff !important; border:1px solid #d9dcef !important; font-weight:700 !important; box-shadow:0 6px 18px -10px rgba(40,50,120,.4); }
        .st-key-moreRow { margin-top:6px; }
        .rs-tbl2 .rs-th { position:sticky; top:-22px; background:#fff; z-index:2; padding-top:22px; margin-top:-22px; }
        .st-key-refresh { margin-top:-3.6rem; margin-bottom:-.4rem; }
        .st-key-refresh [role="radiogroup"] { gap:14px; } .st-key-refresh label p { font-size:13px !important; }
        .st-key-refresh button, .st-key-refresh [data-baseweb="select"] > div { min-height:34px !important; height:34px; font-size:13px !important; border-radius:999px !important; background:#fff !important; border:1px solid #d9dcef !important; }
        .st-key-refresh button p { font-size:13px !important; }
        .st-key-refresh .react-aria-ComboBox [role="group"] { height:34px; min-height:34px; border-radius:999px !important; background:#fff !important; border:1px solid #d9dcef !important; box-shadow:none !important; display:flex; align-items:center; padding:0 10px 0 16px; }
        .st-key-refresh .react-aria-ComboBox input { font-size:13px !important; height:32px !important; padding:0 !important; background:transparent !important; }
        .st-key-refresh .react-aria-ComboBox button { width:20px !important; height:20px !important; min-height:0 !important; padding:0 !important; border:0 !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; display:flex; align-items:center; justify-content:center; margin:0; }
        .st-key-refresh .react-aria-ComboBox svg { width:18px; height:18px; }
        .rs-hero h1 { word-break:keep-all; }
        @media (max-width:560px){ .rs-hero h1{font-size:34px !important} }
        .rs-hero h1 b { font-weight:900; background:linear-gradient(transparent 66%, #cfe8d9 66%); }
        .rs-hero p { color:#5a6076; font-size:15px; margin:18px 0 0; }
        .rs-kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:6px 0 10px; }
        .rs-kpi { background:#fff; border-radius:26px; padding:16px 20px; box-shadow:0 10px 34px rgba(40,50,120,.08); }
        .rs-kpi span { font-size:12.5px; color:#5a6076; }
        .rs-kpi b { display:block; font-size:38px; font-weight:900; letter-spacing:-.03em; line-height:1.1; }
        @media (max-width:900px){ .rs-hero h1{font-size:44px !important; word-break:keep-all} .rs-kpis{grid-template-columns:repeat(2,1fr)} }
        h2, h3 { font-size: 1.5rem !important; }
        </style>""",
        unsafe_allow_html=True)


def hero(small, light, bold, sub=""):
    """페이지 맨 위 큰 제목 (얇은 글씨 + 굵은 글씨 + 연두 밑줄)"""
    st.markdown(f'<div class="rs-hero"><small>{small}</small><h1>{light}<br><b>{bold}</b></h1>' + (f'<p>{sub}</p>' if sub else '') + '</div>', unsafe_allow_html=True)


def kpis(items):
    """숫자 카드 줄: items = [(이름, 값, 색)]"""
    st.markdown('<div class="rs-kpis">' + ''.join(f'<div class="rs-kpi"><span>{n}</span><b style="color:{c}">{v}</b></div>' for n, v, c in items) + '</div>', unsafe_allow_html=True)


def banner(title, result, sub=""):
    """화면 맨 위 큰 판정 표시 (조원 V3 의 종합 판정을 크게) — 얇은 글씨 + 굵은 판정"""
    st.markdown(
        f"""<div style="background:#ffffff;color:#0b0f1e;border-radius:28px;padding:22px 28px;margin:6px 0 14px;box-shadow:0 10px 34px rgba(40,50,120,.09);
        display:flex;align-items:center;gap:20px">
        <div style="flex:none;width:58px;height:58px;border-radius:50%;background:{SOFT[result]};color:{INK[result]};display:grid;place-items:center;font-size:24px">{ICON[result]}</div>
        <div><div style="font-size:13px;color:#5a6076;letter-spacing:.04em">{title}</div>
        <div style="font-size:40px;font-weight:900;line-height:1.15;letter-spacing:-.03em;color:{INK[result]};display:inline-block;background:linear-gradient(transparent 64%,{SOFT[result]} 64%)">{KO[result]}</div>
        <div style="font-size:13.5px;color:#5a6076;margin-top:2px">{sub}</div></div></div>""",
        unsafe_allow_html=True)


def tile(title, result, lines):
    """플랜지 카드: 둥근 흰 카드 + 판정 색 알약 + 큰 판정 글자"""
    body = "<br>".join(lines)
    st.markdown(
        f"""<div style="background:#ffffff;border-radius:24px;padding:14px 18px;margin-bottom:12px;box-shadow:0 10px 34px rgba(40,50,120,.08)">
        <div style="font-size:13px;color:#5a6076">{title}</div>
        <div style="font-size:24px;font-weight:900;letter-spacing:-.02em;color:{INK[result]}">{ICON[result]} {KO[result]}</div>
        <div style="font-size:13px;color:#5a6076;margin-top:4px">{body}</div></div>""",
        unsafe_allow_html=True)


def badge_style(v):
    """표 셀 색칠 (OK/CHECK/NG 또는 한글 판정)"""
    rev = {k_: k for k, k_ in KO.items()} | {k_: k for k, k_ in KO_SHORT.items()}
    r = v if v in COLOR else rev.get(v)
    return f"background-color:{SOFT[r]};color:{INK[r]};font-weight:700" if r else ""


def gauge(title, val, lo, hi, suffix="", fmt=".2f"):
    """기준 범위(초록) 안에 값(파란 막대)이 있는지 보여주는 막대 게이지 (조원 V3)
    축은 기준 범위와 '측정값'이 모두 들어오게 잡고, 색 칸은 축 안으로 잘라서 상자 밖으로 안 튀어나오게 함."""
    span = max(hi - lo, 1e-9)
    pad = .65 * span
    xmin, xmax = lo - pad, hi + pad
    margin = .1 * max(xmax - xmin, 1e-9)
    xmin, xmax = min(xmin, val - margin), max(xmax, val + margin)   # 측정값이 범위 밖이어도 축 안에 보이게
    xmin = max(0, xmin)                                              # 특징값은 모두 0 이상
    if suffix.strip() == "%":
        xmax = min(xmax, 100)                                        # 에너지 비율은 100% 까지
    lo_c, hi_c = max(lo, xmin), min(hi, xmax)                        # 초록 칸도 축 안으로
    inside = lo <= val <= hi
    steps = [{"range": r, "color": c} for r, c in (([xmin, lo_c], "#eef0f4"), ([lo_c, hi_c], BAND),
                                                   ([hi_c, xmax], "#eef0f4")) if r[1] > r[0]]
    f = go.Figure(go.Indicator(
        mode="number+gauge", value=val, domain={"x": [0.32, 1], "y": [0, 1]},
        number={"suffix": suffix, "valueformat": fmt, "font": {"size": 24, "color": COLOR["OK"] if inside else COLOR["NG"]}},
        title={"text": ("✓ " if inside else "✕ ") + title, "font": {"size": 13,
               "color": COLOR["OK"] if inside else COLOR["NG"]}},
        gauge={"shape": "bullet", "axis": {"range": [xmin, xmax]}, "bar": {"color": "#ff6a1f", "thickness": .35},
               "steps": steps, "threshold": {"line": {"color": ACCENT, "width": 4}, "thickness": .8, "value": val}}))
    f.update_layout(height=90, margin=dict(l=10, r=10, t=10, b=20), paper_bgcolor="#ffffff")
    return f


def spectrum_bars(trace, peak_hz, band, label, mag=None, mag_band=None, color="#ff6a1f", compact=False):
    """ESP32 가 보낸 FFT 막대(trace = {f_max, v:[0~100...]})를 그림 (폰·태블릿 화면의 FFT 그래프와 같은 모양).
    주황 막대 = FFT 크기, 연두 박스 = 정상 범위(Peak 주파수 × Peak 크기), 핑크 점 = 이번 Peak (점에 마우스를 올리면 핑크·흰색 말풍선).
    박스 안에 점이 들어오면 정상. 막대가 박스 밖으로 나가도 괜찮음. 그래프를 끌면 확대되고 더블클릭하면 원래대로.
    mag, mag_band 가 없으면(옛 호출) 연두 칸은 세로 띠(Peak 주파수 범위)만 그림."""
    v = trace["v"]
    n, fmax = len(v), trace["f_max"]
    x = [fmax * (i + .5) / n for i in range(n)]
    f = go.Figure(go.Bar(x=x, y=v, width=fmax / n * .72, marker={"color": color, "cornerradius": 4}, hoverinfo="skip"))
    bin_ = min(max(int(peak_hz / fmax * n), 0), n - 1)
    peak_v = max(v[max(bin_ - 1, 0):bin_ + 2])                    # Peak 위치의 막대 높이
    scale = peak_v / mag if mag and mag > 0 and peak_v > 0 else None   # 막대 높이 ↔ 'Peak 크기' 숫자 비율 (그리기용)
    top = max(max(v), 1)
    if band and band[1] > 0:
        px = fmax * .012
        y0, y1 = 0, None
        if scale and mag_band:
            py = .025 * scale
            y0, y1 = max(mag_band[0] * scale - py, 0), mag_band[1] * scale + py
            top = max(top, y1)
        f.add_shape(type="rect", x0=max(band[0] - px, 0), x1=band[1] + px, y0=y0, y1=y1 if y1 is not None else top * 1.12,
                    fillcolor=BAND, line_width=0, layer="below", opacity=.95)
        if y1 is not None:
            for num, yy in ((mag_band[1], y1), (mag_band[0], y0)):
                f.add_annotation(x=0, xref="paper", xanchor="right", y=yy, text=f"{num:.2f}", showarrow=False, font={"size": 11, "color": "#1e90e6"})
    pk_txt = f"{peak_hz / 1000:.2f} kHz" if peak_hz >= 1000 else f"{peak_hz:.0f} Hz"
    f.add_trace(go.Scatter(
        x=[peak_hz], y=[peak_v], mode="markers", showlegend=False,
        marker={"size": 11, "color": PINK, "line": {"color": "#ffffff", "width": 2.5}},
        hovertemplate=f"PEAK 크기<br><b style='font-size:24px'>{(mag if mag else 0):.2f}</b><br>{pk_txt}<extra></extra>",
        hoverlabel={"bgcolor": "#ffffff", "bordercolor": PINK_SOFT, "font": {"color": PINK_INK, "size": 13}, "align": "left"}))
    if compact:      # 시안 E 카드 안 그래프: 축 제목 없이 깔끔하게
        f.update_layout(height=230, margin=dict(l=46, r=14, t=16, b=30), showlegend=False, dragmode="zoom", bargap=0,
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        xaxis={"range": [0, fmax], "showgrid": False, "ticksuffix": " Hz", "tickfont": {"size": 10, "color": "#5a6076"}},
                        yaxis={"range": [0, min(top * 1.12, 130)], "visible": False})
        return f
    f.update_layout(height=260, margin=dict(l=44, r=20, t=24, b=40), showlegend=False, dragmode="zoom", bargap=0,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#f4f5fd",
                    xaxis={"title": "Frequency (Hz)", "range": [0, fmax], "showgrid": False},
                    yaxis={"title": "Magnitude (0~100)", "range": [0, min(top * 1.12, 130)], "gridcolor": "#e3e5f4", "zeroline": False})
    return f


def next_click(title, step, done, total):
    """비전 페이지: 다음에 클릭할 곳 안내 카드"""
    st.markdown(
        f"""<div style="border:2px dashed #ff5900;border-radius:12px;padding:14px 18px;margin-bottom:10px">
        <div style="font-size:13px;opacity:.75">{title} · {done}/{total}</div>
        <div style="font-size:24px;font-weight:700;color:#ff5900">{step}</div></div>""",
        unsafe_allow_html=True)


# ================= 시안 F(검사 현황) · E(타음 검사)용 화면 부품 =================
import math as _math

PAGE_CSS = """<style>
.rs-h2 { margin:34px 0 14px; }
.rs-h2 small { display:block; font-size:13px; letter-spacing:.06em; color:#e0501a; font-weight:500; margin-bottom:6px; }
.rs-h2 div { font-size:44px; line-height:1.06; letter-spacing:-.04em; font-weight:300; color:#0b0f1e; }
.rs-h2 div b { font-weight:900; }
.rs-dark { background:radial-gradient(420px 260px at 85% 0,rgba(96,70,200,.55),transparent 70%),#0b0f2a; color:#fff; border-radius:30px; padding:22px 28px; display:flex; align-items:center; justify-content:space-between; gap:18px; min-height:190px; }
.rs-dark small { color:#a9b0d6; font-size:12px; letter-spacing:.06em; }
.rs-dark .big { font-size:96px; font-weight:900; letter-spacing:-.06em; line-height:1; }
.rs-dark p { color:#a9b0d6; font-size:12.5px; margin:6px 0 0; }
.rs-stat3 { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:12px 0 4px; }
.rs-stat { border-radius:28px; padding:18px 24px; }
.rs-stat span { font-size:13px; font-weight:700; }
.rs-stat b { display:block; font-size:62px; font-weight:900; letter-spacing:-.05em; line-height:1.05; }
.rs-stat .bar { height:5px; border-radius:3px; background:rgba(0,0,0,.08); margin-top:6px; overflow:hidden; }
.rs-stat .bar i { display:block; height:100%; border-radius:3px; }
.rs-stat em { font-style:normal; font-size:12px; opacity:.75; display:block; margin-top:6px; }
.rs-fl { background:#fff; border-radius:26px; padding:14px 16px 14px; box-shadow:0 10px 34px rgba(40,50,120,.08); margin-bottom:14px; }
.rs-fl .t { display:flex; justify-content:space-between; align-items:baseline; }
.rs-fl .t b { font-size:23px; font-weight:900; letter-spacing:-.02em; }
.rs-fl .t span { font-size:11px; color:#5a6076; font-family:ui-monospace,monospace; }
.rs-fl svg { display:block; margin:6px auto; }
.rs-pills { display:flex; gap:5px; flex-wrap:wrap; justify-content:center; }
.rs-pills i { font-style:normal; font-size:11px; font-weight:700; padding:3px 9px; border-radius:99px; }
.rs-trend { background:#0b0f1e; border-radius:30px 30px 0 0; padding:22px 26px 0; color:#fff; margin-top:34px; }
.rs-trend .hd { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; }
.rs-trend b { font-size:22px; font-weight:800; }
.rs-trend span { font-size:11.5px; color:#a9b0d6; }
.rs-tbl { background:#fff; border-radius:30px; padding:10px 26px 16px; box-shadow:0 10px 34px rgba(40,50,120,.07); overflow-x:auto; }
.rs-tbl table { width:100%; border-collapse:collapse; font-size:13.5px; }
.rs-tbl th { text-align:left; font-weight:500; color:#5a6076; font-size:12px; padding:14px 8px 10px; }
.rs-tbl td { padding:11px 8px; border-top:1px solid #f0f1f8; }
.rs-tbl td.m { font-family:ui-monospace,monospace; }
.rs-pill { display:inline-block; padding:4px 12px; border-radius:99px; font-size:12px; font-weight:700; }
.rs-cta { background:#0b0f1e; color:#fff; border-radius:30px; padding:34px 40px; display:flex; justify-content:space-between; align-items:center; gap:20px; margin:34px 0 6px; flex-wrap:wrap; }
.rs-cta div { font-size:40px; font-weight:300; letter-spacing:-.04em; line-height:1.12; }
.rs-cta a { background:#ff5900; color:#fff !important; padding:14px 26px; border-radius:99px; font-weight:700; text-decoration:none; box-shadow:0 12px 30px rgba(255,89,0,.35); }
.rs-wrap3 { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; }
.rs-step { border-radius:30px; padding:26px 30px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center; }
.rs-step small { font-family:ui-monospace,monospace; font-size:12px; opacity:.6; }
.rs-step b { display:block; font-size:72px; font-weight:900; letter-spacing:-.05em; line-height:1; margin:6px 0; }
.rs-step p { margin:0; font-size:14px; opacity:.8; max-width:380px; }
.st-key-trendbox [data-testid="stPlotlyChart"] { background:#0b0f1e !important; border-radius:0 0 30px 30px !important; padding:0 14px 10px !important; box-shadow:none !important; }
.st-key-trendbox { margin-bottom:0; }
div[data-testid="stSegmentedControl"] button, div[role="radiogroup"] label { border-radius:99px !important; }

[data-testid="stMainBlockContainer"] *:has(.rs-ribw) { position:static !important; }
.rs-ribw { position:absolute; left:0; right:0; top:0; bottom:0; z-index:-1; pointer-events:none; overflow:hidden; }
.rs-ribw svg { width:100%; height:100%; display:block; }
.rs-ribw path { stroke-dasharray:1 1; stroke-dashoffset:.8; }
.rs-prog { position:fixed; left:0; top:0; height:4px; width:100%; background:#ff5900; transform-origin:0 50%; transform:scaleX(.02); z-index:1100; pointer-events:none; }
@supports (animation-timeline: scroll()) {
  .stApp { timeline-scope: --rsmain; }
  [data-testid="stMain"] { scroll-timeline: --rsmain block; }
  .rs-ribw path { animation: rsdraw linear both; animation-timeline: --rsmain; }
  .rs-prog { animation: rsprog linear both; animation-timeline: --rsmain; }
}
@keyframes rsdraw { from { stroke-dashoffset:.8; } to { stroke-dashoffset:0; } }
@keyframes rsprog { from { transform:scaleX(0); } to { transform:scaleX(1); } }
[data-testid="stMainBlockContainer"] { position:relative; isolation:isolate; max-width:none !important;
  padding-left:max(24px, calc((100% - 1180px) / 2)) !important; padding-right:max(24px, calc((100% - 1180px) / 2)) !important; }
[data-testid="stMain"] { overflow-x:hidden; }
/* 위쪽 둥근 바: 왼쪽 로고 · 가운데 메뉴 · 오른쪽 상태/폰 앱. 화면 폭 최대 1180px 로 가운데 정렬 */
.st-key-topbar { position:fixed; top:14px; left:50%; transform:translateX(-50%); width:min(1180px, calc(100vw - 48px)); z-index:1000;
  background:rgba(255,255,255,.9); backdrop-filter:blur(14px); border-radius:999px; box-shadow:0 10px 34px rgba(40,50,120,.10); padding:8px 12px 8px 26px; box-sizing:border-box; }
.st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { display:grid !important; grid-template-columns:1fr auto 1fr; align-items:center; gap:12px; flex-wrap:nowrap; }
.st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { width:auto !important; flex:none !important; min-width:0; }
.st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) { justify-self:start; }
.st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { justify-self:center; }
.st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) { justify-self:end; }
.st-key-topbar [data-testid="stLayoutWrapper"] [data-testid="stLayoutWrapper"] [data-testid="stHorizontalBlock"] { display:flex !important; flex-wrap:nowrap !important; gap:8px; align-items:center; }
.st-key-topbar [data-testid="stLayoutWrapper"] [data-testid="stLayoutWrapper"] [data-testid="stColumn"] { width:auto !important; flex:none !important; min-width:0; }
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-topbar { left:calc(50% + 150px); width:min(1180px, calc(100vw - 348px)); }
.stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .rs-prog { left:300px; width:calc(100% - 300px); }
.st-key-herocontrols .stButton > button p { font-size:17px; }
.st-key-topbar p, .st-key-topbar [data-testid="stMarkdownContainer"] { margin:0 !important; }
.rs-brand { font-size:19px; font-weight:800; letter-spacing:-.02em; color:#0b0f1e !important; text-decoration:none !important; white-space:nowrap; }
.st-key-topbar [data-testid="stPageLink"] a { justify-content:center; border-radius:99px; padding:.55rem 1.3rem; font-weight:500; }
.st-key-topbar [data-testid="stPageLink"] a p { white-space:nowrap; }
.rs-conn { margin:0; display:flex; align-items:center; gap:8px; background:#fff; border-radius:99px; padding:9px 16px; font-size:13px; box-shadow:0 2px 10px rgba(40,50,120,.08); white-space:nowrap; }
.rs-conn i { width:8px; height:8px; border-radius:50%; }
.st-key-topbar [data-testid="stLinkButton"] a { background:#ff5900; color:#fff !important; border-radius:99px; border:0; font-weight:700; box-shadow:0 8px 20px rgba(255,89,0,.3); padding:.5rem 1.3rem; white-space:nowrap; }
.st-key-topbar [data-testid="stLinkButton"] a * { color:#fff !important; }
@media (max-width:860px) {
  .st-key-topbar { border-radius:28px; padding:10px 14px; width:calc(100vw - 24px); }
  .st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] { grid-template-columns:1fr auto; grid-template-areas:"a c" "b b"; row-gap:6px; }
  .st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(1) { grid-area:a; }
  .st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(2) { grid-area:b; justify-self:center; }
  .st-key-topbar > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:nth-child(3) { grid-area:c; }
  .stApp:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-topbar { left:50%; width:calc(100vw - 24px); }
  [data-testid="stMainBlockContainer"] { padding-top:8.2rem !important; }
}
@media (max-width:520px) { .rs-conn { display:none; } }
.rs-hero.e small { color:#c0430a; font-family:ui-monospace,monospace; letter-spacing:.14em; }
.rs-hero.e h1 { font-size:68px !important; }
.st-key-herocard iframe { border-radius:40px; box-shadow:0 20px 60px rgba(20,30,100,.25); background:#0b0f1e; }
.st-key-herocontrols { margin-top:26px; }
.st-key-herocontrols [role="radiogroup"], .st-key-filter [role="radiogroup"] { background:rgba(255,255,255,.75); border:1px solid #fff; border-radius:99px; padding:5px; width:fit-content; gap:2px; box-shadow:0 2px 12px rgba(40,50,120,.07); }
[data-testid="stButtonGroup"] button[role="radio"] { border:0 !important; border-radius:99px !important; background:transparent !important; padding:.55rem 1.15rem; box-shadow:none !important; min-height:0; }
[data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] { background:#0b0f1e !important; color:#fff !important; }
[data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] * { color:#fff !important; }
.st-key-herocontrols .stButton > button { height:60px; font-size:17px; padding:0 30px; width:100%; }
.st-key-herocontrols .stButton > button[kind="primary"] { font-weight:700; }
.rs-tbl2 { background:#fff; border-radius:34px; padding:22px 34px 20px; box-shadow:0 10px 34px rgba(40,50,120,.07); overflow-x:auto; }
.rs-th, .rs-tr { display:grid; grid-template-columns:96px 1fr 160px 130px 130px 80px; align-items:center; column-gap:8px; min-width:680px; }
.rs-th { font-size:12px; color:#5a6076; padding:6px 0 10px; }
.rs-tr { height:62px; font-size:14px; }
.rs-tr .tm { font-family:ui-monospace,monospace; color:#5a6076; font-size:13px; }
.rs-tr .nm { font-weight:700; font-size:15px; }
.rs-tr .mn { font-family:ui-monospace,monospace; }
.rs-th span:last-child, .rs-tr .rt { text-align:right; }
.rs-tr .rs-pill { padding:6px 14px; }
.rs-fl circle[data-d] { cursor:pointer; transition:r .12s; }
.rs-fl circle[data-d]:hover { r:7.5; }
.rs-fl circle.sel { stroke:#0b0f1e; stroke-width:2.5; }
.rs-dp { margin:10px 0 6px; }
.rs-tr[data-d] { cursor:pointer; border-radius:18px; transition:background .15s; }
.rs-tr[data-d]:hover { background:#f5f6fe; }
.rs-tr.open { background:#f5f6fe; }
.rs-tr.open .nm::after { content:" ▴"; color:#ff5900; font-size:11px; }
.rs-tr[data-d]:not(.open) .nm::after { content:" ▾"; color:#9aa1b8; font-size:11px; }
.rs-hd { background:#f5f6fe; border-radius:26px; padding:20px 22px 16px; margin:4px 0 14px; min-width:680px; }
.rs-hd .hxh { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:14px; }
.rs-hd .hxh b { font-size:18px; font-weight:800; }
.rs-hd .hxh span { font-size:13px; color:#5a6076; font-family:ui-monospace,monospace; }
.rs-hd .hxh em { font-style:normal; font-size:12px; font-weight:700; padding:5px 12px; border-radius:99px; }
.rs-hd .hxh small { font-size:12px; color:#5a6076; margin-left:auto; }
.rs-hd .hxg { display:grid; grid-template-columns:1fr 1fr; gap:18px; }
.rs-hd .hxcard { background:#fff; border-radius:26px; padding:20px 24px 22px; box-shadow:0 6px 22px rgba(40,50,120,.06); min-width:0; }
.rs-hd .rs-evh b { font-size:24px; }
.rs-hd .hxc { position:relative; height:190px; margin:8px 0 0 0; background:#f5f6fe; border-radius:18px; }
.rs-hd .hxb { position:absolute; bottom:0; border-radius:3px 3px 0 0; }
.rs-hd .hxbox { position:absolute; border-radius:12px; background:#cfe8d9; opacity:.95; }
.rs-hd .hxd { position:absolute; width:11px; height:11px; margin:-5.5px 0 0 -5.5px; border-radius:50%; background:#ff3d81; border:2.5px solid #fff; box-sizing:content-box; box-shadow:0 2px 8px rgba(255,61,129,.5); }
.rs-hd .hxt { position:relative; height:20px; margin-top:4px; font-size:10px; color:#5a6076; }
.rs-hd .hxt span { position:absolute; top:0; }
.rs-hd .hxn { font-size:12.5px; color:#5a6076; margin:10px 0 0; }
.rs-hd .hxf { font-size:12px; color:#5a6076; margin:14px 2px 0; }
@media (max-width:900px) { .rs-hd .hxg { grid-template-columns:1fr; } }


.rs-evh { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:12px; }
.rs-evh b { font-size:30px; font-weight:800; letter-spacing:-.03em; }
.rs-evh span { font-family:ui-monospace,monospace; font-size:11px; letter-spacing:.1em; color:#5a6076; }
.st-key-evc_mic, .st-key-evc_acc { background:#fff; border-radius:34px; padding:26px 30px 30px; box-shadow:0 10px 34px rgba(40,50,120,.07); }
.st-key-evc_mic [data-testid="stPlotlyChart"], .st-key-evc_acc [data-testid="stPlotlyChart"] { background:#f5f6fe !important; border-radius:24px !important; box-shadow:none !important; padding:6px 0 0 !important; }
.rs-slw { margin-top:8px; }
.rs-sl { margin:16px 0 4px; }
.rs-slt { display:flex; justify-content:space-between; font-size:14px; color:#3a4056; }
.rs-slt b { font-family:ui-monospace,monospace; font-weight:500; font-size:14px; }
.rs-slb { position:relative; height:8px; background:#eceef9; border-radius:4px; margin-top:8px; }
.rs-slb .rng { position:absolute; top:0; bottom:0; background:#cfe8d9; border-radius:4px; }
.rs-slb .dot { position:absolute; top:50%; width:22px; height:22px; margin:-11px 0 0 -11px; background:#ff5900; border:3px solid #fff; border-radius:7px; box-shadow:0 2px 8px rgba(255,89,0,.4); box-sizing:border-box; }
.rs-stack { padding-bottom:6px; }
.rs-st2 { position:sticky; height:380px; border-radius:40px; margin-bottom:28px; padding:0 52px; display:flex; align-items:center; justify-content:space-between; gap:20px; box-shadow:0 20px 50px rgba(30,40,120,.14); box-sizing:border-box; overflow:hidden; }
.rs-st2 small { font-family:ui-monospace,monospace; font-size:13px; opacity:.6; letter-spacing:.1em; }
.rs-st2 b { display:block; font-size:clamp(64px, 10vw, 128px); line-height:1; letter-spacing:-.06em; font-weight:900; margin:14px 0 18px; }
.rs-st2 p { margin:0; max-width:430px; font-size:15.5px; line-height:1.7; opacity:.82; }
.rs-st2 .ill { flex:none; }
@media (max-width:860px) { .rs-st2 { padding:0 26px; height:320px; } .rs-st2 .ill { display:none; } }
.st-key-basecard { background:#fff; border-radius:40px; padding:44px 44px 36px; box-shadow:0 10px 34px rgba(40,50,120,.07); }
.rs-base small { color:#e0501a; font-size:13px; letter-spacing:.06em; }
.rs-base h2 { font-size:clamp(34px,4.4vw,52px) !important; line-height:1.08; font-weight:300 !important; letter-spacing:-.04em; margin:10px 0 22px; padding:0; }
.rs-base h2 b { font-weight:900; }
.rs-circ { display:grid; grid-template-columns:repeat(10,minmax(0,1fr)); gap:6px; margin:0 0 20px; max-width:560px; }
.rs-circ i { width:100%; max-width:44px; aspect-ratio:1; height:auto; border-radius:50%; display:grid; place-items:center; font-style:normal; font-size:13px; border:1.5px dashed #b9bdd6; color:#7a8099; }
.rs-circ i.on { background:#ff5900; border-color:#ff5900; color:#fff; }
.st-key-basecard .stButton > button[kind="primary"] { height:52px; padding:0 28px; }
.st-key-btn_save button { background:#0b0f1e !important; color:#fff !important; height:52px; padding:0 28px; }
.st-key-btn_save button:disabled { opacity:.35; }
.rs-bst { padding-top:6px; }
.rs-bsh, .rs-bs { display:flex; justify-content:space-between; align-items:center; }
.rs-bsh { font-size:12px; color:#5a6076; padding:0 20px 12px; }
.rs-bs { height:54px; padding:0 20px; border-radius:18px; font-size:15px; }
.rs-bs.alt { background:#f4f5fd; }
.rs-bs em { font-style:normal; color:#e0501a; font-size:11px; margin-right:12px; }
.rs-bs b { font-family:ui-monospace,monospace; font-weight:500; font-size:14px; }
.rs-rcs { display:flex; gap:16px; overflow-x:auto; scroll-snap-type:x mandatory; padding:8px 4px 26px; margin:0 -4px; }
.rs-rc { flex:0 0 300px; scroll-snap-align:start; background:#fff; border-radius:30px; padding:22px 24px; box-shadow:0 10px 34px rgba(40,50,120,.08); }
.rs-rc .top { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#5a6076; font-family:ui-monospace,monospace; }
.rs-rc b { display:block; font-size:36px; font-weight:900; letter-spacing:-.04em; margin:14px 0 14px; }
.rs-rc .bars { display:flex; align-items:flex-end; gap:5px; height:58px; }
.rs-rc .bars i { flex:1; border-radius:3px; }
.rs-rc .bt { display:flex; justify-content:space-between; font-size:12.5px; color:#3a4056; margin-top:14px; }
.rs-hrow { display:flex; justify-content:space-between; align-items:flex-end; gap:12px; }

@media (max-width:900px){ .rs-stat3,.rs-wrap3{grid-template-columns:1fr} .rs-h2 div{font-size:32px} .rs-dark .big{font-size:64px} .rs-cta div{font-size:28px} }
</style>"""


def page_css():
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


def h2(small, light, bold):
    sm = f"<small>{small}</small>" if small else ""
    st.markdown(f'<div class="rs-h2">{sm}<div>{light}<br><b>{bold}</b></div></div>', unsafe_allow_html=True)


def donut(pct, color="#8fe0b4", size=130):
    r = 52
    c = 2 * _math.pi * r
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 130 130"><circle cx="65" cy="65" r="{r}" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="13"/>'
            f'<circle cx="65" cy="65" r="{r}" fill="none" stroke="{color}" stroke-width="13" stroke-linecap="round" stroke-dasharray="{c * pct / 100:.1f} {c:.1f}" transform="rotate(-90 65 65)"/>'
            f'<text x="65" y="66" text-anchor="middle" fill="#fff" font-size="26" font-weight="800">{pct:.0f}%</text>'
            f'<text x="65" y="84" text-anchor="middle" fill="#a9b0d6" font-size="11">정상</text></svg>')


def dark_total(label, number, foot, pct):
    st.markdown(f'<div class="rs-dark"><div><small>{label}</small><div class="big">{number}</div><p>{foot}</p></div>{donut(pct)}</div>', unsafe_allow_html=True)


def stat3(counts, total):
    """정상/재측정/이상 큰 숫자 카드 3개 (counts = {'OK':n,'CHECK':n,'NG':n})"""
    names = {"OK": ("정상", "#d9f2e4", "#14633f", "#2fa36b"), "CHECK": ("재측정 필요", "#ffebc2", "#7a5200", "#e8a317"),
             "NG": ("체결 이상 의심", "#ffd9d6", "#8e2019", "#e0443a")}
    out = ""
    for k, (nm, bg, fg, bar) in names.items():
        n = counts.get(k, 0)
        share = 100 * n / total if total else 0
        out += (f'<div class="rs-stat" style="background:{bg};color:{fg}"><span>{nm}</span><b>{n}</b>'
                f'<div class="bar"><i style="width:{share:.0f}%;background:{bar}"></i></div><em>전체의 {share:.0f}%</em></div>')
    st.markdown(f'<div class="rs-stat3">{out}</div>', unsafe_allow_html=True)


def ring_card(fid, stamp, dots, n_ok, n_chk, n_ng, bolts=None, details=None, row=0):
    """플랜지 카드: 볼트 개수만큼 원 모양으로 점을 놓고 판정 색으로 칠함. dots = [판정 or None, ...]
    bolts = 점마다 볼트 번호, details = 점마다 FFT 펼침 정보(없으면 None) → 있으면 점을 눌러 FFT 를 볼 수 있음"""
    import html as _h
    import json as _j
    n = max(len(dots), 1)
    cs = ""
    for i, d in enumerate(dots):
        a = -_math.pi / 2 + 2 * _math.pi * i / n
        col = {"OK": "#2fa36b", "CHECK": "#e8a317", "NG": "#e0443a"}.get(d, "#e3e5f1")
        det = details[i] if details and i < len(details) else None
        attr = ""
        if det:
            attr = (f' data-k="{_h.escape(fid)}-{_h.escape(str(bolts[i]))}" '
                    f'data-r="{row}" data-d="{_h.escape(_j.dumps(det, ensure_ascii=False, separators=(",", ":")), quote=True)}"')
        cs += f'<circle cx="{50 + 33 * _math.cos(a):.1f}" cy="{50 + 33 * _math.sin(a):.1f}" r="6" fill="{col}"{attr}/>'
    st.markdown(
        f'<div class="rs-fl"><div class="t"><b>{fid}</b><span>{stamp}</span></div>'
        f'<svg width="100" height="100" viewBox="0 0 100 100">{cs}</svg><div class="rs-pills">'
        f'<i style="background:#d9f2e4;color:#14633f">정상 {n_ok}</i><i style="background:#ffebc2;color:#7a5200">재측정 {n_chk}</i>'
        f'<i style="background:#ffd9d6;color:#8e2019">의심 {n_ng}</i></div></div>', unsafe_allow_html=True)


def dot_panel(row=0):
    """플랜지 카드 한 줄 바로 아래, 그 줄의 점을 눌렀을 때 FFT 카드가 열릴 자리 (줄마다 하나씩 놓음)"""
    st.html(f'<div id="rs-dotpanel-{row}"></div><script>{_js("fft_panel.js", "dot_panel.js")}</script>', unsafe_allow_javascript=True)


def pill(res):
    return f'<span class="rs-pill" style="background:{SOFT[res]};color:{INK[res]}">{KO[res]}</span>'


def table_card(head, rows, max_h=None):
    """시안 F 의 '최근 측정 기록' 표: 줄 없이 넓은 행, 판정은 알약. rows = [[시간, 이름, 판정HTML, 음향, 진동, 개수]]"""
    th = "".join(f"<span>{h}</span>" for h in head)
    body = ""
    for r in rows:
        body += (f'<div class="rs-tr"><span class="tm">{r[0]}</span><span class="nm">{r[1]}</span><span>{r[2]}</span>'
                 f'<span class="mn">{r[3]}</span><span class="mn">{r[4]}</span><span class="mn rt">{r[5]}</span></div>')
    sty = f' style="max-height:{max_h}px;overflow-y:auto"' if max_h else ""
    st.markdown(f'<div class="rs-tbl2"{sty}><div class="rs-th">{th}</div>{body}</div>', unsafe_allow_html=True)


_JS_CACHE = {}


def _js(*names, **repl):
    """dashboard/ 안의 .js 파일들을 이어 붙여 base64 로 감싼 한 줄 스크립트로 만듦.
    st.html 은 스크립트 안에 "<" 글자가 있으면 스크립트를 실행하지 못해서, 코드를 base64 글자로 감싸 넣고 화면에서 풀어 실행함."""
    import base64 as _b64
    from pathlib import Path as _P
    src = ""
    for n in names:
        if n not in _JS_CACHE:
            _JS_CACHE[n] = (_P(__file__).with_name(n)).read_text(encoding="utf-8")
        src += _JS_CACHE[n] + "\n"
    for k, v in repl.items():
        src = src.replace(k, v)
    return ('(function(){var b=atob("' + _b64.b64encode(src.encode("utf-8")).decode() + '"),u=new Uint8Array(b.length);'
            'for(var i=0;i!=b.length;i++)u[i]=b.charCodeAt(i);(0,eval)(new TextDecoder().decode(u))})()')


def hist_table(head, rows, ids, details, max_h=None, key="hist"):
    """전체 검사 기록 표 (table_card 와 같은 모양). 행을 누르면 바로 아래에 그때 측정한 FFT 가 열리고, 다시 누르면 닫힘.
    ids = 행마다 고유 번호(record_id), details = 행마다 {n,t,r,f,sp,ref,src} 또는 None(타음 측정이 아닌 기록: 눌러도 안 열림)"""
    import html as _h
    import json as _j
    tid = f"rs-{key}"
    js = _js("fft_panel.js", "hist_table.js", __ID__=tid)
    th = "".join(f"<span>{h}</span>" for h in head)
    body = ""
    for r, rid, d in zip(rows, ids, details):
        attr = ""
        if d:
            attr = (f' data-id="{_h.escape(str(rid), quote=True)}" data-d="{_h.escape(_j.dumps(d, ensure_ascii=False, separators=(",", ":")), quote=True)}"'
                    ' role="button" tabindex="0" aria-expanded="false"')
        body += (f'<div class="rs-tr"{attr}><span class="tm">{r[0]}</span><span class="nm">{r[1]}</span><span>{r[2]}</span>'
                 f'<span class="mn">{r[3]}</span><span class="mn">{r[4]}</span><span class="mn rt">{r[5]}</span></div>')
    sty = f' style="max-height:{max_h}px;overflow-y:auto"' if max_h else ""
    st.html(f'<div class="rs-tbl2" id="{tid}"{sty}><div class="rs-th">{th}</div>{body}</div><script>{js}</script>',
            unsafe_allow_javascript=True)


def cta(text_html, label, href):
    st.markdown(f'<div class="rs-cta"><div>{text_html}</div><a href="{href}" target="_self">{label} →</a></div>', unsafe_allow_html=True)


def trend_dark(title, sub, xs, ys, band=None):
    f = go.Figure()
    if band:
        f.add_hrect(y0=band[0], y1=band[1], fillcolor="rgba(143,224,180,.16)", line_width=0)
    f.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line={"color": "#ff8a3d", "width": 2.4, "shape": "spline", "smoothing": .5}, hovertemplate="%{y:,.0f} Hz<extra></extra>"))
    f.update_layout(height=250, margin=dict(l=8, r=8, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis={"visible": False}, yaxis={"showgrid": False, "color": "#a9b0d6", "zeroline": False}, showlegend=False)
    st.markdown(f'<div class="rs-trend"><div class="hd"><b>{title}</b><span>{sub}</span></div></div>', unsafe_allow_html=True)
    with st.container(key="trendbox"):
        st.plotly_chart(f, width="stretch", key="trendfig", config={"displayModeBar": False})


def verdict_hero(eyebrow, result, chips, bolt_no=1):
    """시안 E 왼쪽 위: 'TAP INSPECTION · F-03 · BOLT 04' + '4번 볼트는 / 정상이에요.' + 칩. result=None 이면 아직 측정 전"""
    if result is None:
        head = f'{bolt_no}번 볼트를<br><b>두드려 볼까요?</b>'
        cs = ""
    else:
        word = {"OK": "정상", "CHECK": "재측정이 필요", "NG": "체결 이상이 의심"}[result]
        tail = {"OK": "이에요.", "CHECK": "해요.", "NG": "돼요."}[result]
        hl = {"OK": "#c5ead4", "CHECK": "#ffe3a3", "NG": "#ffc9c4"}[result]
        head = (f'{bolt_no}번 볼트는<br><b style="background:linear-gradient(transparent 70%,{hl} 70%);color:{INK[result]};font-weight:900">{word}</b>{tail}')
        cs = "".join(
            f'<i style="font-style:normal;border-radius:99px;padding:10px 18px;font-size:14px;font-weight:{700 if n == 0 else 500};'
            f'background:{SOFT[result] if n == 0 else "#fff"};color:{INK[result] if n == 0 else "#0b0f1e"}">{c}</i>' for n, c in enumerate(chips))
    st.markdown(f'<div class="rs-hero e"><small>TAP INSPECTION · {eyebrow}</small><h1>{head}</h1>'
                f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">{cs}</div></div>', unsafe_allow_html=True)


def tap_hero(label, status, foot):
    """시안 E 오른쪽: 3D 볼트가 돌아가는 어두운 카드 (tap_hero.html 을 그대로 보여 줌)"""
    from pathlib import Path
    p = Path(__file__).resolve().parent / "tap_hero.html"
    if not p.exists():
        st.caption("tap_hero.html 을 찾지 못했어요 (dashboard 폴더에 있어야 해요).")
        return
    html = p.read_text(encoding="utf-8").replace("__LABEL__", label).replace("__STATUS__", status).replace("__FOOT__", foot)
    if hasattr(st, "iframe"):
        st.iframe(html, height=540)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=540)


def rule_tiles(score, check, ng):
    """벗어난 항목 개수 규칙 3칸 — 이번 측정이 해당하는 칸은 진하게"""
    items = [("OK", "정상", "0" if check <= 1 else f"0 ~ {check - 1}", range(0, check)), ("CHECK", "재측정 필요", f"{check}", range(check, ng)),
             ("NG", "체결 이상 의심", f"{ng}+", range(ng, 99))]
    out = ""
    for k, nm, num, rg in items:
        on = score in rg
        out += (f'<div class="rs-stat" style="background:{SOFT[k]};color:{INK[k]};opacity:{1 if on else .45};{"outline:3px solid " + COLOR[k] if on else ""}">'
                f'<span>{nm}</span><b>{num}</b><em>벗어난 항목 {num}개{" · 이번 측정" if on else ""}</em></div>')
    st.markdown(f'<div class="rs-stat3">{out}</div>', unsafe_allow_html=True)


def flow_cards():
    st.markdown("""<div class="rs-wrap3"><div class="rs-step" style="background:#fff"><div><small>01</small><b>TAP</b><p>솔레노이드가 볼트를 매번 같은 세기로 한 번 칩니다. 손으로 칠 때는 8초 동안 기다려요.</p></div></div>
<div class="rs-step" style="background:#3a3df0;color:#fff"><div><small>02</small><b>HEAR</b><p>마이크와 진동센서 신호를 주파수로 바꿔 Peak 주파수, Peak 크기, 대역 에너지를 뽑아요.</p></div></div>
<div class="rs-step" style="background:#0b0f1e;color:#fff"><div><small>03</small><b>VERIFY</b><p>정상 볼트로 만든 기준 범위와 비교해 정상, 재측정 필요, 체결 이상 의심으로 알려줘요.</p></div></div></div>""", unsafe_allow_html=True)


def ribbon():
    """뒤 배경 파란 선: 페이지 전체 길이에 걸쳐 있고, 스크롤을 내릴수록 이어서 그려지며 올리면 다시 사라짐 (CSS 스크롤 애니메이션,
    크롬·엣지·사파리 최신판). 지원 안 하는 브라우저는 앞부분만 보이는 상태로 고정. 위쪽 주황 진행선도 같이."""
    st.markdown(
        '<div class="rs-ribw"><svg viewBox="0 0 1440 4400" preserveAspectRatio="none" fill="none" aria-hidden="true">'
        '<defs><linearGradient id="rsr" gradientUnits="userSpaceOnUse" x1="200" y1="0" x2="1240" y2="4400"><stop offset="0" stop-color="#92FAFC"/>'
        '<stop offset=".45" stop-color="#4FD8F2"/><stop offset="1" stop-color="#2A9FE2"/></linearGradient></defs>'
        f'<path pathLength="1" d="{RIBBON_D}" stroke="url(#rsr)" stroke-width="48" stroke-linecap="round" stroke-linejoin="round"/></svg></div>'
        '<div class="rs-prog"></div>', unsafe_allow_html=True)


def topbar(p_tap, p_home, connected, active="", app_url="https://bolt-inspect.web.app/app/"):
    """시안의 위쪽 둥근 바: RE:SOUND(소개 페이지로) / 타음 검사 / 검사 현황 / 연결 상태 / 폰 앱"""
    st.markdown(f'<style>.st-key-topbar a[href$="{active}"][data-testid="stPageLink-NavLink"] {{ background:#0b0f1e !important; }}'
                f'.st-key-topbar a[href$="{active}"][data-testid="stPageLink-NavLink"] * {{ color:#fff !important; }}</style>' if active else "", unsafe_allow_html=True)
    with st.container(key="topbar"):
        a, b, c = st.columns([1.15, 2, 1.55], vertical_alignment="center")
        a.markdown('<a class="rs-brand" href="/" target="_self">RE<span style="color:#ff5900">:</span>SOUND</a>', unsafe_allow_html=True)
        with b:
            n1, n2 = st.columns(2)
            n1.page_link(p_tap, label="타음 검사")
            n2.page_link(p_home, label="검사 현황")
        with c:
            d, e = st.columns([1.35, 1], vertical_alignment="center")
            d.markdown(f'<div class="rs-conn"><i style="background:{"#2fa36b" if connected else "#9aa1b8"}"></i>{"연결됨" if connected else "내 PC 저장"}</div>', unsafe_allow_html=True)
            e.link_button("폰 앱", app_url, type="primary")


def footer():
    st.markdown('<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;color:#5a6076;font-size:13px;margin:18px 4px 30px">'
                '<span>RE:SOUND · 거제 2조</span><span>배정호 · 송건호 · 안지민 · 양세영 · 오대관 · 이승현 · 이현태</span></div>', unsafe_allow_html=True)


# ---------- 시안 E: 증거 카드 · 흐름 카드 · 기준 만들기 · 최근 측정 카드 ----------
def ev_head(title, tag):
    st.markdown(f'<div class="rs-evh"><b>{title}</b><span>{tag}</span></div>', unsafe_allow_html=True)


def slider_rows(rows):
    """Peak 주파수 / Peak 크기 / 대역 에너지: 연두 칸 = 정상 범위, 주황 점 = 이번 값.
    rows = [(이름, 값 글자, 값, 하한, 상한, 단위꼴 '% 여부')]"""
    out = ""
    for name, txt, v, lo, hi, pct in rows:
        span = max(hi - lo, 1e-9)
        a0, a1 = lo - .65 * span, hi + .65 * span
        a0, a1 = min(a0, v - .1 * span), max(a1, v + .1 * span)
        a0 = max(a0, 0)
        if pct:
            a1 = min(a1, 100)
        w = max(a1 - a0, 1e-9)
        pos = lambda x: 100 * min(max((x - a0) / w, 0), 1)
        ok = lo <= v <= hi
        out += (f'<div class="rs-sl"><div class="rs-slt"><span>{name}</span><b style="color:{"#0b0f1e" if ok else "#c0302a"}">{txt}</b></div>'
                f'<div class="rs-slb"><i class="rng" style="left:{pos(lo):.1f}%;width:{pos(hi) - pos(lo):.1f}%"></i>'
                f'<i class="dot" style="left:{pos(v):.1f}%"></i></div></div>')
    st.markdown(f'<div class="rs-slw">{out}</div>', unsafe_allow_html=True)


def flow_stack():
    """TAP / HEAR / VERIFY: 스크롤하면 카드가 한 장씩 위로 쌓이며 넘어감"""
    bars = [10, 22, 28, 32, 26, 38, 30, 20, 16, 14, 56, 90, 70, 100, 82, 120, 150, 120, 96, 60, 40, 36, 18, 22, 8, 18, 22, 10, 10]
    wave = "".join(f'<rect class="a-eq" style="animation-delay:-{(i * 0.37) % 1.3:.2f}s;animation-duration:{0.9 + (i % 5) * 0.1:.1f}s" x="{i * 14}" y="{80 - h / 2:.0f}" width="7" height="{h}" rx="3.5" fill="#fff"/>' for i, h in enumerate(bars))
    tap = ('<svg width="280" height="200" viewBox="0 0 280 200" fill="none"><rect x="10" y="168" width="260" height="26" rx="13" fill="#CFD3EE"/>'
           '<rect x="88" y="92" width="104" height="76" rx="18" fill="#0B0F1E"/><rect x="102" y="66" width="76" height="34" rx="8" fill="#FF8A3D"/>'
           '<g class="a-rod"><rect x="125" y="14" width="30" height="70" rx="10" fill="#FF5900"/></g>'
           '<path class="a-arc" d="M58 98q-14 18 0 40M222 98q14 18 0 40" stroke="#FFAF80" stroke-width="5" stroke-linecap="round"/></svg>')
    ver = ('<svg width="240" height="240" viewBox="0 0 260 260" fill="none"><circle cx="130" cy="130" r="108" stroke="rgba(245,246,255,.16)" stroke-width="16"/>'
           '<circle class="a-ring" cx="130" cy="130" r="108" stroke="#8EF0BE" stroke-width="16" stroke-linecap="round" pathLength="100" stroke-dasharray="100 100" transform="rotate(-90 130 130)"/>'
           '<path class="a-chk" pathLength="100" d="M84 134l32 32 62-72" stroke="#8EF0BE" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    card = lambda n, big, txt, bg, fg, ill, top: (
        f'<div class="rs-st2" style="background:{bg};color:{fg};top:{top}px"><div><small>{n}</small><b>{big}</b><p>{txt}</p></div><div class="ill">{ill}</div></div>')
    st.markdown('<div class="rs-stack">'
                + card("01", "TAP", "솔레노이드가 볼트를 매번 같은 세기로 한 번 칩니다. 손으로 칠 때는 8초 동안 기다려요.", "#fff", "#0b0f1e", tap, 96)
                + card("02", "HEAR", "마이크와 진동센서 신호를 주파수로 바꿔 Peak 주파수, Peak 크기, 대역 에너지를 뽑아냅니다.", "#3347ff", "#fff",
                       f'<svg width="400" height="160" viewBox="0 0 400 160">{wave}</svg>', 112)
                + card("03", "VERIFY", "정상 볼트로 만든 기준 범위와 비교해 정상, 재측정 필요, 체결 이상 의심으로 알려줘요.", "#0b0f1e", "#f5f6ff", ver, 128)
                + '</div>', unsafe_allow_html=True)


def base_circles(n_total, n_done):
    c = "".join(f'<i class="{"on" if i < n_done else ""}">{i + 1}</i>' for i in range(n_total))
    return f'<div class="rs-circ">{c}</div>'


def base_stats(rows):
    """rows = [(센서, 이름, '평균 ± 표준편차' 글자)]"""
    body = "".join(f'<div class="rs-bs{" alt" if i % 2 == 0 else ""}"><span><em>{s}</em>{n}</span><b>{v}</b></div>' for i, (s, n, v) in enumerate(rows))
    st.markdown(f'<div class="rs-bst"><div class="rs-bsh"><span>특징값</span><span>평균 ± 표준편차</span></div>{body}</div>', unsafe_allow_html=True)


def recent_cards(items):
    """items = [{res, time, name, bars[0~1], mic, acc}]  — 옆으로 넘겨 보는 카드"""
    col = {"OK": "#2fa36b", "CHECK": "#e0a21f", "NG": "#e0443a"}
    out = ""
    for it in items:
        c = col.get(it["res"], "#9aa1b8")
        if it["bars"]:
            bars = f'<div class="bars">' + "".join(f'<i style="height:{max(6, 56 * b):.0f}px;background:{c}"></i>' for b in it["bars"]) + '</div>'
        else:      # 저장된 스펙트럼이 없으면 Peak 주파수 위치를 같은 눈금 위에 점으로
            mx = max(it.get("mic_hz") or 0, it.get("acc_hz") or 0, 1) * 1.15
            row = lambda nm, hz, col: (f'<div class="pk"><span>{nm}</span><div class="tr"><i style="left:{100 * hz / mx:.1f}%;background:{col}"></i></div></div>' if hz else "")
            bars = f'<div style="height:58px;display:flex;flex-direction:column;justify-content:center;gap:4px">{row("음향", it.get("mic_hz"), "#ff5900")}{row("진동", it.get("acc_hz"), "#3347ff")}</div>'
        out += (f'<div class="rs-rc"><div class="top">{pill(it["res"])}<span>{it["time"]}</span></div><b>{it["name"]}</b>'
                f'{bars}<div class="bt"><span>음향 {it["mic"]}</span><span>진동 {it["acc"]}</span></div></div>')
    st.markdown(f'<div class="rs-rcs">{out}</div>', unsafe_allow_html=True)
