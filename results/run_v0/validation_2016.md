| check                                                    | dev           | src/run                |    abs diff | status   |
|:---------------------------------------------------------|:--------------|:-----------------------|------------:|:---------|
| events_R1 rows                                           | 10507         | 10467                  |   40        | DIFF     |
| events_R1 key sets equal                                 | 0             | 1                      |    1        | DIFF     |
| events_R1 max abs diff over all float columns (don_L)    | 0.0           | 1918.7119903564453     | 1920        | DIFF     |
| events_R1 NaN-pattern mismatches                         | 0             | 2760                   | 2760        | DIFF     |
| events_R3 rows                                           | 53067         | 52857                  |  210        | DIFF     |
| events_R3 key sets equal                                 | 0             | 1                      |    1        | DIFF     |
| events_R3 max abs diff over all float columns (don_pjmA) | 0.0           | 1886.1058066685946     | 1890        | DIFF     |
| events_R3 NaN-pattern mismatches                         | 0             | 2730                   | 2730        | DIFF     |
| events_erosion rows                                      | 42028         | 41868                  |  160        | DIFF     |
| events_erosion max abs diff                              | 0.0           | 3511.5999999999985     | 3510        | DIFF     |
| H1 site Bear                                             | -0.0296       | -0.029640973559212525  |    4.1e-05  | OK       |
| H1 site Bull                                             | -0.0125       | -0.012515665919943807  |    1.57e-05 | OK       |
| H1 site Cockatoo                                         | -0.0318       | -0.03182907449416626   |    2.91e-05 | OK       |
| H1 site Eagle                                            | -0.0117       | -0.010893509667916485  |    0.000806 | DIFF     |
| H1 site Fox                                              | -0.0257       | -0.025747193303395456  |    4.72e-05 | OK       |
| H1 site Hog                                              | -0.0703       | -0.07026634715656079   |    3.37e-05 | OK       |
| H1 site Lamb                                             | 0.2774        | 0.2773900779310085     |    9.92e-06 | OK       |
| H1 site Peacock                                          | -0.0133       | -0.013294387923813645  |    5.61e-06 | OK       |
| H1 site Rat                                              | -0.1402       | -0.14020736894688257   |    7.37e-06 | OK       |
| H1 site Robin                                            | -0.0858       | -0.08576027498106903   |    3.97e-05 | OK       |
| H1 site Wolf                                             | -0.0213       | -0.0213062874966031    |    6.29e-06 | OK       |
| H1 HL                                                    | -0.0262       | -0.02615743714939007   |    4.26e-05 | OK       |
| H1 CI low                                                | -0.0764       | -0.07636151743341318   |    3.85e-05 | OK       |
| H1 CI high                                               | 0.0686        | 0.06859135449206297    |    8.65e-06 | OK       |
| H2 site Bear                                             | -0.4018       | -0.4017532574107963    |    4.67e-05 | OK       |
| H2 site Bull                                             | -0.1808       | -0.18076653806395637   |    3.35e-05 | OK       |
| H2 site Cockatoo                                         | -0.1495       | -0.14952327090654932   |    2.33e-05 | OK       |
| H2 site Eagle                                            | 0.0726        | 0.09057994024757239    |    0.018    | DIFF     |
| H2 site Fox                                              | -0.3909       | -0.3908538249260256    |    4.62e-05 | OK       |
| H2 site Hog                                              | -0.4402       | -0.4402045197983572    |    4.52e-06 | OK       |
| H2 site Lamb                                             | -0.5003       | -0.5003037661379088    |    3.77e-06 | OK       |
| H2 site Peacock                                          | -0.1162       | -0.11621829460041805   |    1.83e-05 | OK       |
| H2 site Rat                                              | -0.8106       | -0.8106330665699133    |    3.31e-05 | OK       |
| H2 site Robin                                            | -0.528        | -0.5279897317053107    |    1.03e-05 | OK       |
| H2 site Wolf                                             | -0.6941       | -0.6941012011762796    |    1.2e-06  | OK       |
| H2 HL                                                    | -0.3936       | -0.39357868304721827   |    2.13e-05 | OK       |
| H2 CI low                                                | -0.5672       | -0.5671528604873184    |    4.71e-05 | OK       |
| H2 CI high                                               | -0.1651       | -0.16514490448525285   |    4.49e-05 | OK       |
| H3 site Bear                                             | 0.0098        | 0.009751986619900458   |    4.8e-05  | OK       |
| H3 site Bull                                             | -0.0027       | -0.0027207563602859326 |    2.08e-05 | OK       |
| H3 site Cockatoo                                         | 0.0689        | 0.06891247626783477    |    1.25e-05 | OK       |
| H3 site Eagle                                            | -0.0004       | 0.010466898849231413   |    0.0109   | DIFF     |
| H3 site Fox                                              | 0.0089        | 0.00889023766753448    |    9.76e-06 | OK       |
| H3 site Hog                                              | 0.3149        | 0.3149460233997665     |    4.6e-05  | OK       |
| H3 site Lamb                                             | 0.128         | 0.1279793478056691     |    2.07e-05 | OK       |
| H3 site Peacock                                          | -0.0148       | -0.014816904273263359  |    1.69e-05 | OK       |
| H3 site Rat                                              | -0.0431       | -0.043085892151647986  |    1.41e-05 | OK       |
| H3 site Robin                                            | 0.0842        | 0.08415967531150684    |    4.03e-05 | OK       |
| H3 site Wolf                                             | 0.0256        | 0.025572040288786558   |    2.8e-05  | OK       |
| H3 HL                                                    | 0.0345        | 0.036786371243403185   |    0.00229  | DIFF     |
| H3 CI low                                                | -0.0015       | 0.0030847406536242735  |    0.00458  | DIFF     |
| H3 CI high                                               | 0.0984        | 0.09844591203675193    |    4.59e-05 | OK       |
| H1 signed-rank p                                         | 0.02685546875 | 0.02685546875          |    0        | OK       |
| H2 signed-rank p                                         | 0.0009765625  | 0.0009765625           |    0        | OK       |
| H3 p_lower                                               | 0.00048828125 | 0.00048828125          |    0        | OK       |
| H3 p_upper                                               | 0.05078125    | 0.05078125             |    0        | OK       |
| H3 p_TOST                                                | 0.05078125    | 0.05078125             |    0        | OK       |
| H4 site p-cross Bear                                     | 0.0513        | 0.0513                 |    0        | OK       |
| H4 site p-cross Bull                                     | 0.0253        | 0.0253                 |    0        | OK       |
| H4 site p-cross Cockatoo                                 | 0.0236        | 0.0236                 |    0        | OK       |
| H4 site p-cross Eagle                                    | 0.0066        | 0.0098                 |    0.0032   | DIFF     |
| H4 site p-cross Fox                                      | 0.0302        | 0.0302                 |    0        | OK       |
| H4 site p-cross Hog                                      | 0.0597        | 0.0597                 |    0        | OK       |
| H4 site p-cross Lamb                                     | 0.0           | 0.0                    |    0        | OK       |
| H4 site p-cross Peacock                                  | 0.0243        | 0.0243                 |    0        | OK       |
| H4 site p-cross Rat                                      | 0.0529        | 0.0529                 |    0        | OK       |
| H4 site p-cross Robin                                    | 0.0848        | 0.0848                 |    0        | OK       |
| H4 site p-cross Wolf                                     | 0.0562        | 0.0562                 |    0        | OK       |
| H4 sign-test p                                           | 0.00048828125 | 0.00048828125          |    0        | OK       |
| H4 signed-rank sensitivity p (censored ranked largest)   | 0.00048828125 | 0.00048828125          |    0        | OK       |
| H4 median site p-cross                                   | 0.0302        | 0.0302                 |    0        | OK       |
| H4 order-stat CI low                                     | 0.0066        | 0.0098                 |    0.0032   | DIFF     |
| H4 order-stat CI high                                    | 0.0597        | 0.0597                 |    0        | OK       |
| H4 pooled p-cross                                        | 0.0415        | 0.0423                 |    0.0008   | DIFF     |
| p* pooled pjmA                                           | 0.0921        | 0.0919                 |    0.0002   | DIFF     |
| p* pooled scmr_W7_l3                                     | >0.30         | >0.30                  |             | OK       |
| p* pooled caisoA                                         | 0.1049        | 0.1048                 |    0.0001   | OK       |
| p* pooled cgA                                            | 0.0893        | 0.0892                 |    0.0001   | DIFF     |
| p* pooled pjm0                                           | >0.30         | >0.30                  |             | OK       |
| H5 support events per K                                  | 10462         | 10422                  |   40        | DIFF     |
| H5abs site Bear                                          | -0.00327      | -0.003269008492542811  |    9.92e-07 | OK       |
| H5abs site Bull                                          | -0.00118      | -0.0011828586086492527 |    2.86e-06 | OK       |
| H5abs site Cockatoo                                      | -0.00182      | -0.0018161279568401803 |    3.87e-06 | OK       |
| H5abs site Eagle                                         | -0.00086      | -0.0012317660034198482 |    0.000372 | DIFF     |
| H5abs site Fox                                           | -0.00133      | -0.0013320583194859734 |    2.06e-06 | OK       |
| H5abs site Hog                                           | -0.0027       | -0.0026975244340281465 |    2.48e-06 | OK       |
| H5abs site Lamb                                          | -0.00362      | -0.003623210498382688  |    3.21e-06 | OK       |
| H5abs site Peacock                                       | -0.00065      | -0.0006455811200896686 |    4.42e-06 | OK       |
| H5abs site Rat                                           | -0.00241      | -0.0024127292705837847 |    2.73e-06 | OK       |
| H5abs site Robin                                         | -0.00702      | -0.007015606026412174  |    4.39e-06 | OK       |
| H5abs site Wolf                                          | -0.00193      | -0.0019285012870181284 |    1.5e-06  | OK       |
| H5abs HL                                                 | -0.00215      | -0.0021982744146984944 |    4.83e-05 | OK       |
| H5abs HL ci low                                          | -0.00383      | -0.0038305935732509213 |    5.94e-07 | OK       |
| H5abs HL ci high                                         | -0.00129      | -0.0012870412035538986 |    2.96e-06 | OK       |
| H5abs two-sided p                                        | 0.0009765625  | 0.0009765625           |    0        | OK       |
| H5abs pooled eta pjmA                                    | 0.00186       | 0.00186                |    0        | OK       |
| H5abs pooled eta scmr_W7_l3                              | 0.00392       | 0.00399                |    7e-05    | OK       |
| H5abs pooled eta caisoA                                  | 0.0037        | 0.00383                |    0.00013  | DIFF     |
| H5abs pooled eta pjm0                                    | 0.00847       | 0.00828                |    0.00019  | DIFF     |
| H5abs pooled eta cgA                                     | 0.00225       | 0.0023                 |    5e-05    | OK       |
| age days pjm_lookback K=10                               | 5.5           | 5.5                    |    0        | OK       |
| age days scmR_preperiod K=10                             | 7.29          | 7.29                   |    0        | OK       |
| age days pjm_lookback K=20                               | 7.5           | 7.5                    |    0        | OK       |
| age days scmR_preperiod K=20                             | 9.0           | 9.0                    |    0        | OK       |
| age days pjm_lookback K=30                               | 9.25          | 9.25                   |    0        | OK       |
| age days scmR_preperiod K=30                             | 12.29         | 12.29                  |    0        | OK       |
| age days pjm_lookback K=40                               | 12.0          | 12.0                   |    0        | OK       |
| age days scmR_preperiod K=40                             | 16.0          | 16.0                   |    0        | OK       |
| H5 signed rho pjmA K=10                                  | 0.983         | 0.9843                 |    0.0013   | DIFF     |
| H5 signed rho pjmA K=20                                  | 0.9638        | 0.9638                 |    0        | OK       |
| H5 signed rho pjmA K=30                                  | 0.9559        | 0.9561                 |    0.0002   | DIFF     |
| H5 signed rho pjmA K=40                                  | 0.9344        | 0.9336                 |    0.0008   | DIFF     |
| H5 signed pooled eta pjmA                                | 0.00153       | 0.0016                 |    7e-05    | OK       |
| H5 signed rho caisoA K=10                                | 0.9423        | 0.9428                 |    0.0005   | DIFF     |
| H5 signed rho caisoA K=20                                | 0.9253        | 0.9255                 |    0.0002   | DIFF     |
| H5 signed rho caisoA K=30                                | 0.9074        | 0.9044                 |    0.003    | DIFF     |
| H5 signed rho caisoA K=40                                | 0.8729        | 0.872                  |    0.0009   | DIFF     |
| H5 signed pooled eta caisoA                              | 0.00226       | 0.00233                |    7e-05    | OK       |
| H5 signed rho pjm0 K=10                                  | 0.9012        | 0.9033                 |    0.0021   | DIFF     |
| H5 signed rho pjm0 K=20                                  | 0.8557        | 0.8567                 |    0.001    | DIFF     |
| H5 signed rho pjm0 K=30                                  | 0.8203        | 0.8198                 |    0.0005   | DIFF     |
| H5 signed rho pjm0 K=40                                  | 0.7576        | 0.7573                 |    0.0003   | DIFF     |
| H5 signed pooled eta pjm0                                | 0.00466       | 0.00475                |    9e-05    | OK       |
| H5 signed rho cgA K=10                                   | 0.9903        | 0.9914                 |    0.0011   | DIFF     |
| H5 signed rho cgA K=20                                   | 0.9907        | 0.9909                 |    0.0002   | DIFF     |
| H5 signed rho cgA K=30                                   | 0.9883        | 0.989                  |    0.0007   | DIFF     |
| H5 signed rho cgA K=40                                   | 0.9582        | 0.9585                 |    0.0003   | DIFF     |
| H5 signed pooled eta cgA                                 | 0.00099       | 0.00101                |    2e-05    | OK       |
| H5 signed contrast HL (secondary)                        | 0.0021        | 0.0021912993249348224  |    9.13e-05 | OK       |
| fallback PJM K=10                                        | 0.0           | 0.0                    |    0        | OK       |
| fallback CAISO K=10                                      | 0.0001        | 0.0001                 |    0        | OK       |
| fallback PJM K=40                                        | 0.0466        | 0.0468                 |    0.0002   | DIFF     |
| fallback CAISO K=40                                      | 0.048         | 0.0482                 |    0.0002   | DIFF     |
| scm grid scmr_W7_l3                                      | 0.0612        | 0.0618                 |    0.0006   | DIFF     |
| scm grid scmr_W5_l3                                      | 0.0618        | 0.0619                 |    0.0001   | OK       |
| scm grid scmr_W3_l1                                      | 0.062         | 0.0624                 |    0.0004   | DIFF     |
| scm grid scmr_W5_l1                                      | 0.0622        | 0.0625                 |    0.0003   | DIFF     |
| scm grid scmc_W5                                         | 0.0665        | 0.0667                 |    0.0002   | DIFF     |
| scm grid scmc_W3                                         | 0.067         | 0.0675                 |    0.0005   | DIFF     |
| scm grid scmc_W7                                         | 0.0682        | 0.0686                 |    0.0004   | DIFF     |
| scm grid best ridge config                               | scmr_W7_l3    | scmr_W7_l3             |             | OK       |
| method R1 prev relMAE median                             | 0.0724        | 0.0725                 |    0.0001   | OK       |
| method R1 prev bias median                               | -0.0175       | -0.0174                |    0.0001   | DIFF     |
| method R1 pjm0 relMAE median                             | 0.0806        | 0.0813                 |    0.0007   | DIFF     |
| method R1 pjm0 bias median                               | -0.0093       | -0.0092                |    0.0001   | OK       |
| method R1 pjmA relMAE median                             | 0.0474        | 0.0475                 |    0.0001   | DIFF     |
| method R1 pjmA bias median                               | -0.0019       | -0.0018                |    0.0001   | DIFF     |
| method R1 caiso0 relMAE median                           | 0.0886        | 0.0892                 |    0.0006   | DIFF     |
| method R1 caiso0 bias median                             | -0.0256       | -0.0258                |    0.0002   | DIFF     |
| method R1 caisoA relMAE median                           | 0.0496        | 0.0496                 |    0        | OK       |
| method R1 caisoA bias median                             | -0.0056       | -0.0056                |    0        | OK       |
| method R1 ny0 relMAE median                              | 0.078         | 0.0781                 |    0.0001   | DIFF     |
| method R1 ny0 bias median                                | 0.0088        | 0.0092                 |    0.0004   | DIFF     |
| method R1 nyA relMAE median                              | 0.0555        | 0.0555                 |    0        | OK       |
| method R1 nyA bias median                                | 0.01          | 0.0099                 |    0.0001   | OK       |
| method R1 isone0 relMAE median                           | 0.0886        | 0.089                  |    0.0004   | DIFF     |
| method R1 isone0 bias median                             | -0.0256       | -0.0258                |    0.0002   | DIFF     |
| method R1 isoneA relMAE median                           | 0.0463        | 0.0464                 |    0.0001   | OK       |
| method R1 isoneA bias median                             | -0.0078       | -0.0077                |    0.0001   | OK       |
| method R1 dm0 relMAE median                              | 0.0886        | 0.0892                 |    0.0006   | DIFF     |
| method R1 dm0 bias median                                | -0.0256       | -0.0258                |    0.0002   | DIFF     |
| method R1 dmA relMAE median                              | 0.0549        | 0.0548                 |    0.0001   | OK       |
| method R1 dmA bias median                                | -0.0068       | -0.0068                |    0        | OK       |
| method R1 wm0 relMAE median                              | 0.0803        | 0.0812                 |    0.0009   | DIFF     |
| method R1 wm0 bias median                                | -0.0138       | -0.014                 |    0.0002   | DIFF     |
| method R1 wmA relMAE median                              | 0.0577        | 0.0577                 |    0        | OK       |
| method R1 wmA bias median                                | -0.001        | -0.001                 |    0        | OK       |
| method R1 m3 relMAE median                               | 0.0708        | 0.0714                 |    0.0006   | DIFF     |
| method R1 m3 bias median                                 | 0.0149        | 0.015                  |    0.0001   | OK       |
| method R1 mid8 relMAE median                             | 0.0886        | 0.0888                 |    0.0002   | DIFF     |
| method R1 mid8 bias median                               | -0.0255       | -0.0255                |    0        | OK       |
| method R1 cg0 relMAE median                              | 0.0796        | 0.0798                 |    0.0002   | DIFF     |
| method R1 cg0 bias median                                | 0.0097        | 0.0101                 |    0.0004   | DIFF     |
| method R1 cgA relMAE median                              | 0.0516        | 0.0519                 |    0.0003   | DIFF     |
| method R1 cgA bias median                                | -0.001        | -0.0009                |    0.0001   | DIFF     |
| method R1 scmR relMAE median                             | 0.0612        | 0.0618                 |    0.0006   | DIFF     |
| method R1 scmR bias median                               | 0.0083        | 0.0082                 |    0.0001   | OK       |
| method R1 scmC relMAE median                             | 0.0665        | 0.0667                 |    0.0002   | DIFF     |
| method R1 scmC bias median                               | 0.0108        | 0.0109                 |    0.0001   | OK       |
| method R3 prev relMAE median                             | 0.0724        | 0.0728                 |    0.0004   | DIFF     |
| method R3 prev bias median                               | 0.0047        | 0.0049                 |    0.0002   | DIFF     |
| method R3 pjm0 relMAE median                             | 0.0823        | 0.0826                 |    0.0003   | DIFF     |
| method R3 pjm0 bias median                               | 0.0329        | 0.0331                 |    0.0002   | DIFF     |
| method R3 pjmA relMAE median                             | 0.0553        | 0.0557                 |    0.0004   | DIFF     |
| method R3 pjmA bias median                               | 0.0072        | 0.0072                 |    0        | OK       |
| method R3 caiso0 relMAE median                           | 0.0875        | 0.0878                 |    0.0003   | DIFF     |
| method R3 caiso0 bias median                             | 0.0106        | 0.0107                 |    0.0001   | OK       |
| method R3 caisoA relMAE median                           | 0.0559        | 0.056                  |    0.0001   | DIFF     |
| method R3 caisoA bias median                             | 0.0034        | 0.0034                 |    0        | OK       |
| method R3 ny0 relMAE median                              | 0.1149        | 0.115                  |    0.0001   | DIFF     |
| method R3 ny0 bias median                                | 0.0806        | 0.0809                 |    0.0003   | DIFF     |
| method R3 nyA relMAE median                              | 0.0732        | 0.0733                 |    0.0001   | DIFF     |
| method R3 nyA bias median                                | 0.0303        | 0.0305                 |    0.0002   | DIFF     |
| method R3 isone0 relMAE median                           | 0.0875        | 0.0878                 |    0.0003   | DIFF     |
| method R3 isone0 bias median                             | 0.0106        | 0.0107                 |    0.0001   | OK       |
| method R3 isoneA relMAE median                           | 0.0527        | 0.0533                 |    0.0006   | DIFF     |
| method R3 isoneA bias median                             | 0.0016        | 0.0016                 |    0        | OK       |
| method R3 dm0 relMAE median                              | 0.0875        | 0.0878                 |    0.0003   | DIFF     |
| method R3 dm0 bias median                                | 0.0106        | 0.0107                 |    0.0001   | OK       |
| method R3 dmA relMAE median                              | 0.0614        | 0.0614                 |    0        | OK       |
| method R3 dmA bias median                                | 0.0035        | 0.0035                 |    0        | OK       |
| method R3 wm0 relMAE median                              | 0.1039        | 0.1042                 |    0.0003   | DIFF     |
| method R3 wm0 bias median                                | 0.007         | 0.0071                 |    0.0001   | DIFF     |
| method R3 wmA relMAE median                              | 0.0667        | 0.0668                 |    0.0001   | DIFF     |
| method R3 wmA bias median                                | 0.0036        | 0.0036                 |    0        | OK       |
| method R3 m3 relMAE median                               | 0.1155        | 0.1162                 |    0.0007   | DIFF     |
| method R3 m3 bias median                                 | 0.0926        | 0.0929                 |    0.0003   | DIFF     |
| method R3 mid8 relMAE median                             | 0.0873        | 0.0874                 |    0.0001   | DIFF     |
| method R3 mid8 bias median                               | 0.0104        | 0.0105                 |    0.0001   | DIFF     |
| DST table identical                                      | 1             | 1                      |    0        | OK       |