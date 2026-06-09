==============================================================================
DHS DOWNLOADS — REFERENCE & INVENTORY
==============================================================================


Surveys  : 2014 datasets across 36 countries, 46 recode types

Each zip is also extracted into a same-named folder next to it.
Stata files inside .DT zips end in .DTA  (read with pyreadstat / pandas).
Shapefiles inside .FL GPS zips include .shp/.shx/.dbf/.prj  (read with geopandas).

------------------------------------------------------------------------------
FILENAME ANATOMY  —  e.g.  ZWBR72DT.zip
------------------------------------------------------------------------------

  Z W   B R   7 2   D T   . zip
  └─┘   └─┘   └─┘   └─┘
   |     |     |     └── format suffix (DT=Stata, FL=Flat/GPS, SP=SPSS, SR=SAS)
   |     |     └────── phase + version  (72 = DHS Phase 7, version 2)
   |     └──────────── recode type     (BR = Births Recode)
   └────────────────── country code    (ZW = Zimbabwe)

DHS survey phases:
  1 = DHS-I    (1986-1990)
  2 = DHS-II   (1988-1993)
  3 = DHS-III  (1992-1998)
  4 = DHS-IV   (1997-2003)
  5 = DHS-V    (2003-2008)
  6 = DHS-VI   (2008-2013)
  7 = DHS-VII  (2013-2019)
  8 = DHS-VIII (2018-2023)
  9 = DHS-IX   (2023- )

------------------------------------------------------------------------------
RECODE CODES SEEN IN YOUR DOWNLOADS
------------------------------------------------------------------------------

  AI  Accidents/Injuries Recode (SPA)
        Accident & injury services data.

  AN  Antenatal Care Recode (SPA)
        Provider-client antenatal observations.

  AR  HIV Test Results Recode
        One row per person with a DHS HIV blood test. Recode form — link to IR/MR/PR by cluster+household+line.

  AT  ART (SPA)
        Antiretroviral therapy services data.

  BQ  Biomarker Questionnaire
        Raw biomarker (HIV / anaemia) testing data.

  BR  Births Recode
        One row per birth ever reported by interviewed women. Use for fertility, child mortality, birth-spacing analysis.

  CL  Client (SPA)
        Exit-interview client data.

  CN  Consultations (SPA)
        General consultation records.

  CO  Country Specific (SPA)
        Country-specific SPA module.

  CR  Couples' Recode
        One row per cohabiting couple where both partners were interviewed. Concordance of contraceptive use, fertility preferences, HIV status, etc.

  CS  Country Specific (SPA, alt)
        Country-specific SPA module.

  CT  Community Recode
        Community / village questionnaire.

  FC  Facility Inventory (SPA)
        Facility-level audit data.

  FP  Family Planning Recode (SPA)
        Provider-client family-planning observations.

  GE  Geographic Data (GPS cluster coordinates)
        Shapefile (points). One feature per DHS sample cluster. Key fields: DHSCLUST (= v001/hv001), LATNUM, LONGNUM, URBAN_RURA, ALT_DEM.

  GR  Pregnancy and Postnatal Care Recode
        Per-pregnancy details — replaces older ANC/PNC sections in newer phases.

  HH  Household Raw
        Raw household data file (pre-recode).

  HR  Household Recode
        One row per household. Dwelling characteristics, assets, water/sanitation, deaths in past year.

  HT  Health Information System (SPA)
        Health information system audit.

  HW  Height and Weight Scores (WHO Child Growth Standards)
        Anthropometric z-scores for children under 5. Merge with KR/PR on cluster+household+line.

  IN  Inpatient (SPA)
        Inpatient unit data.

  IP  Inpatient/Outpatient (SPA)
        Combined inpatient/outpatient data.

  IQ  Individual Raw (Women)
        Raw women's questionnaire (pre-recode).

  IR  Individual Recode (Women)
        One row per woman aged 15-49 interviewed. Main women's questionnaire — contraception, fertility, ANC, child health, attitudes.

  KR  Children's Recode
        One row per living child under age 5 (born in last ~5 yrs). Use for immunisation, nutrition, illness, anthropometry of young children.

  LB  Labor & Delivery (SPA)
        L&D unit / observations.

  LD  Labor & Delivery alt (SPA)
        Labor and delivery recode (alt).

  ML  Malaria (SPA)
        Malaria-specific services / commodities.

  MR  Men's Recode
        One row per man (typically 15-49 or 15-59) interviewed. Subset of households only.

  MS  Men's Raw
        Raw men's questionnaire (pre-recode).

  NR  Pregnancies Recode
        One row per pregnancy ever reported (live births, stillbirths, miscarriages).

  OD  Other Data
        Country-specific / one-off recode file.

  OI  Outpatient/Inpatient (SPA)
        Outpatient and inpatient combined.

  OP  Outpatient (SPA)
        Outpatient unit data.

  PH  Pharmacy (SPA)
        Pharmacy / commodities.

  PM  PMTCT (SPA)
        Prevention of mother-to-child HIV transmission.

  PR  Household Member Recode
        One row per household member (de jure & de facto). Roster + education, anthropometry, anaemia for all measured members.

  PV  Provider (SPA)
        Provider questionnaire/interview.

  SC  Sick Child Recode (SPA)
        Provider-client observations of sick child consultations.

  SI  Safe Injection (SPA)
        Safe injection practices audit.

  SL  Staff / Provider Listing (SPA)
        Roster of facility staff.

  SQ  Service Provision recode (SPA)
        SPA service-provision module.

  SR  Siblings Recode
        One row per sibling of the female respondent. Used for adult-mortality / maternal-mortality estimates.

  TB  TB Data (SPA)
        Tuberculosis services data.

  VA  Verbal Autopsy
        Likely cause of death from interviews with relatives of deceased.

  WI  Wealth Index
        Pre-computed household wealth quintiles using principal-components on assets.

------------------------------------------------------------------------------
COUNTRY CODES
------------------------------------------------------------------------------

  AO  Angola                        
  BF  Burkina Faso
  BJ  Benin                         
  BU  Burundi
  CD  Congo Democratic Republic     
  CF  Central African Republic
  CI  Cote d'Ivoire                 
  CM  Cameroon
  ET  Ethiopia                      
  GA  Gabon
  GH  Ghana                         
  GM  Gambia
  GN  Guinea                        
  KE  Kenya
  KM  Comoros                       
  LB  Liberia
  LS  Lesotho                       
  MD  Madagascar
  ML  Mali                          
  MR  Mauritania
  MW  Malawi                        
  MZ  Mozambique
  NG  Nigeria                       
  NI  Niger
  NM  Namibia                       
  RW  Rwanda
  SL  Sierra Leone                  
  SN  Senegal
  SZ  Eswatini (Swaziland)          
  TD  Chad
  TG  Togo                          
  TZ  Tanzania
  UG  Uganda                        
  ZA  South Africa
  ZM  Zambia                        
  ZW  Zimbabwe

------------------------------------------------------------------------------
FILE FORMAT SUFFIXES SEEN
------------------------------------------------------------------------------

  DT  Stata system file (.dta)
  FL  Flat ASCII (.dat / shapefile bundle for GPS)
  SP  SPSS system file (.sav)
  SR  SAS system file (.sas7bdat)

Your survey downloads are Stata (DT) — open with:
    import pyreadstat
    df, meta = pyreadstat.read_dta(r'...\AO\IR\AOIR71DT\AOIR71FL.DTA',
                                   apply_value_formats=True)

Your GPS downloads are Flat shapefiles (FL) — open with:
    import geopandas as gpd
    gps = gpd.read_file(r'...\AO\GE\AOGE71FL\AOGE71FL.shp')

------------------------------------------------------------------------------
LINKING SURVEYS  <->  GPS
------------------------------------------------------------------------------

DHS cluster ID is the join key:
    survey  v001  (women/men/births)        <->   shapefile  DHSCLUST
    survey  hv001 (household / hh-member)   <->   shapefile  DHSCLUST

Surveys from the SAME survey share the same cluster IDs. So you can
join Individual + Children + Household to GPS in one go.

Geographic displacement: DHS jitters each cluster point for privacy —
urban clusters by up to 2 km, rural by up to 5 km (1% by up to 10 km).
Treat coordinates as 'cluster centroid + noise'.

------------------------------------------------------------------------------
VARIABLE NAMING CONVENTION (inside the .DTA files)
------------------------------------------------------------------------------

DHS uses consistent variable prefixes across surveys and countries:

  v000-v999    Woman's questionnaire vars (IR, BR, KR, CR)
    v000       country code + phase  (e.g. 'AO7' = Angola Phase VII)
    v001       cluster number   <-- the GPS join key
    v002       household number
    v003       respondent's line number
    v005       sample weight (divide by 1,000,000)
    v007       year of interview
    v012       respondent's current age
    v024       region
    v025       urban/rural
    v106       highest educational level
    v190      wealth-index quintile

  hv000-hv999  Household vars (HR, PR)
    hv001      cluster number   <-- the GPS join key
    hv002      household number
    hv005      sample weight

  mv*          Men's questionnaire (MR) — same numbering, m-prefixed
  hml*         Household members / malaria module
  hc*          Household-member child anthropometry

Each .DTA has full variable labels and value labels embedded — open with
apply_value_formats=True in pyreadstat to keep them.

------------------------------------------------------------------------------
YOUR INVENTORY (by country)
------------------------------------------------------------------------------

  [AO] Angola  —  32 files across 12 recode types
      AR  HIV Test Results Recode  (2):  AOAR71DT, AOAR81DT
      BR  Births Recode  (3):  AOBR62DT, AOBR71DT, AOBR81DT
      CR  Couples' Recode  (2):  AOCR71DT, AOCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  AOGE52FL, AOGE61FL, AOGE71FL, AOGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  AOGR81DT
      HR  Household Recode  (4):  AOHR51DT, AOHR62DT, AOHR71DT, AOHR81DT
      IR  Individual Recode (Women)  (4):  AOIR51DT, AOIR62DT, AOIR71DT, AOIR81DT
      KR  Children's Recode  (4):  AOKR51DT, AOKR62DT, AOKR71DT, AOKR81DT
      MR  Men's Recode  (2):  AOMR71DT, AOMR81DT
      NR  Pregnancies Recode  (1):  AONR81DT
      PR  Household Member Recode  (4):  AOPR51DT, AOPR62DT, AOPR71DT, AOPR81DT
      SR  Siblings Recode  (1):  AOSR81DT

  [BF] Burkina Faso  —  61 files across 15 recode types
      AR  HIV Test Results Recode  (2):  BFAR41DT, BFAR61DT
      BR  Births Recode  (5):  BFBR21DT, BFBR31DT, BFBR43DT, BFBR62DT, BFBR81DT
      CR  Couples' Recode  (5):  BFCR21DT, BFCR31DT, BFCR41DT, BFCR62DT, BFCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (7):  BFGE23FL, BFGE32FL, BFGE43FL, BFGE61FL, BFGE71FL, BFGE7AFL, BFGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  BFGR81DT
      HR  Household Recode  (7):  BFHR21DT, BFHR31DT, BFHR43DT, BFHR62DT, BFHR71DT, BFHR7ADT, BFHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  BFHW21DT, BFHW31DT, BFHW43DT
      IR  Individual Recode (Women)  (7):  BFIR21DT, BFIR31DT, BFIR43DT, BFIR62DT, BFIR71DT, BFIR7ADT, BFIR81DT
      KR  Children's Recode  (7):  BFKR21DT, BFKR31DT, BFKR43DT, BFKR62DT, BFKR71DT, BFKR7ADT, BFKR81DT
      MR  Men's Recode  (5):  BFMR21DT, BFMR31DT, BFMR41DT, BFMR62DT, BFMR81DT
      NR  Pregnancies Recode  (1):  BFNR81DT
      PR  Household Member Recode  (7):  BFPR21DT, BFPR31DT, BFPR44DT, BFPR62DT, BFPR71DT, BFPR7ADT, BFPR81DT
      SQ  Service Provision recode (SPA)  (1):  BFSQ22DT
      SR  Siblings Recode  (1):  BFSR81DT
      WI  Wealth Index  (2):  BFWI21DT, BFWI31DT

  [BJ] Benin  —  46 files across 11 recode types
      BR  Births Recode  (5):  BJBR31DT, BJBR41DT, BJBR51DT, BJBR61DT, BJBR71DT
      CR  Couples' Recode  (5):  BJCR31DT, BJCR41DT, BJCR51DT, BJCR61DT, BJCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  BJGE33FL, BJGE42FL, BJGE61FL, BJGE71FL
      HR  Household Recode  (5):  BJHR31DT, BJHR41DT, BJHR51DT, BJHR61DT, BJHR71DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  BJHW31DT, BJHW41DT
      IR  Individual Recode (Women)  (5):  BJIR31DT, BJIR41DT, BJIR51DT, BJIR61DT, BJIR71DT
      KR  Children's Recode  (5):  BJKR31DT, BJKR41DT, BJKR51DT, BJKR61DT, BJKR71DT
      MR  Men's Recode  (5):  BJMR31DT, BJMR41DT, BJMR51DT, BJMR61DT, BJMR71DT
      PR  Household Member Recode  (5):  BJPR31DT, BJPR41DT, BJPR51DT, BJPR61DT, BJPR71DT
      SQ  Service Provision recode (SPA)  (3):  BJSQ38DT, BJSQ41DT, BJSQ51DT
      WI  Wealth Index  (2):  BJWI31DT, BJWI41DT

  [BU] Burundi  —  29 files across 12 recode types
      AR  HIV Test Results Recode  (2):  BUAR61DT, BUAR71DT
      BR  Births Recode  (3):  BUBR01DT, BUBR61DT, BUBR71DT
      CR  Couples' Recode  (2):  BUCR61DT, BUCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (3):  BUGE61FL, BUGE6AFL, BUGE71FL
      HH  Household Raw  (1):  BUHH02DT
      HR  Household Recode  (3):  BUHR61DT, BUHR6ADT, BUHR71DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (1):  BUHW01DT
      IR  Individual Recode (Women)  (4):  BUIR02DT, BUIR61DT, BUIR6ADT, BUIR71DT
      KR  Children's Recode  (4):  BUKR01DT, BUKR61DT, BUKR6ADT, BUKR71DT
      MR  Men's Recode  (2):  BUMR61DT, BUMR71DT
      PR  Household Member Recode  (3):  BUPR61DT, BUPR6ADT, BUPR71DT
      SQ  Service Provision recode (SPA)  (1):  BUSQ02DT

  [CD] Congo Democratic Republic  —  37 files across 18 recode types
      AN  Antenatal Care Recode (SPA)  (1):  CDAN71DTSP
      AR  HIV Test Results Recode  (3):  CDAR51DT, CDAR61DT, CDAR81DT
      BR  Births Recode  (3):  CDBR51DT, CDBR61DT, CDBR81DT
      CR  Couples' Recode  (3):  CDCR51DT, CDCR61DT, CDCR81DT
      FC  Facility Inventory (SPA)  (1):  CDFC71DTSP
      FP  Family Planning Recode (SPA)  (1):  CDFP71DTSP
      GE  Geographic Data (GPS cluster coordinates)  (4):  CDGE52FL, CDGE61FL, CDGE71FLSR, CDGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  CDGR81DT
      HR  Household Recode  (3):  CDHR51DT, CDHR61DT, CDHR81DT
      IR  Individual Recode (Women)  (3):  CDIR51DT, CDIR61DT, CDIR81DT
      KR  Children's Recode  (3):  CDKR51DT, CDKR61DT, CDKR81DT
      MR  Men's Recode  (3):  CDMR51DT, CDMR61DT, CDMR81DT
      NR  Pregnancies Recode  (1):  CDNR81DT
      PR  Household Member Recode  (3):  CDPR51DT, CDPR61DT, CDPR81DT
      PV  Provider (SPA)  (1):  CDPV71DTSP
      SC  Sick Child Recode (SPA)  (1):  CDSC71DTSP
      SL  Staff / Provider Listing (SPA)  (1):  CDSL71DTSP
      SR  Siblings Recode  (1):  CDSR81DT

  [CF] Central African Republic  —  11 files across 11 recode types
      BR  Births Recode  (1):  CFBR31DT
      CR  Couples' Recode  (1):  CFCR31DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  CFGE33FL
      HR  Household Recode  (1):  CFHR31DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (1):  CFHW31DT
      IR  Individual Recode (Women)  (1):  CFIR31DT
      KR  Children's Recode  (1):  CFKR31DT
      MR  Men's Recode  (1):  CFMR31DT
      PR  Household Member Recode  (1):  CFPR31DT
      SQ  Service Provision recode (SPA)  (1):  CFSQ33DT
      WI  Wealth Index  (1):  CFWI31DT

  [CI] Cote d'Ivoire  —  47 files across 15 recode types
      AR  HIV Test Results Recode  (2):  CIAR51DT, CIAR61DT
      BR  Births Recode  (5):  CIBR35DT, CIBR3ADT, CIBR51DT, CIBR62DT, CIBR81DT
      CR  Couples' Recode  (4):  CICR35DT, CICR3ADT, CICR62DT, CICR81DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  CIGE33FL, CIGE3BFL, CIGE61FL, CIGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  CIGR81DT
      HR  Household Recode  (5):  CIHR35DT, CIHR3ADT, CIHR51DT, CIHR62DT, CIHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  CIHW35DT, CIHW3ADT
      IR  Individual Recode (Women)  (5):  CIIR35DT, CIIR3ADT, CIIR51DT, CIIR62DT, CIIR81DT
      KR  Children's Recode  (5):  CIKR35DT, CIKR3ADT, CIKR51DT, CIKR62DT, CIKR81DT
      MR  Men's Recode  (4):  CIMR33DT, CIMR3ADT, CIMR62DT, CIMR81DT
      NR  Pregnancies Recode  (1):  CINR81DT
      PR  Household Member Recode  (5):  CIPR35DT, CIPR3ADT, CIPR51DT, CIPR62DT, CIPR81DT
      SQ  Service Provision recode (SPA)  (1):  CISQ33DT
      SR  Siblings Recode  (1):  CISR81DT
      WI  Wealth Index  (2):  CIWI34DT, CIWI3ADT

  [CM] Cameroon  —  53 files across 12 recode types
      AR  HIV Test Results Recode  (3):  CMAR42DT, CMAR61DT, CMAR71DT
      BR  Births Recode  (5):  CMBR22DT, CMBR31DT, CMBR44DT, CMBR61DT, CMBR71DT
      CR  Couples' Recode  (5):  CMCR21DT, CMCR31DT, CMCR44DT, CMCR61DT, CMCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (5):  CMGE23FL, CMGE42FL, CMGE61FL, CMGE71FL, CMGE81FL
      HR  Household Recode  (6):  CMHR22DT, CMHR31DT, CMHR44DT, CMHR61DT, CMHR71DT, CMHR82DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  CMHW22DT, CMHW31DT, CMHW44DT
      IR  Individual Recode (Women)  (6):  CMIR22DT, CMIR31DT, CMIR44DT, CMIR61DT, CMIR71DT, CMIR82DT
      KR  Children's Recode  (6):  CMKR21DT, CMKR31DT, CMKR44DT, CMKR61DT, CMKR71DT, CMKR82DT
      MR  Men's Recode  (5):  CMMR21DT, CMMR31DT, CMMR44DT, CMMR61DT, CMMR71DT
      PR  Household Member Recode  (6):  CMPR22DT, CMPR31DT, CMPR45DT, CMPR61DT, CMPR71DT, CMPR82DT
      SQ  Service Provision recode (SPA)  (1):  CMSQ21DT
      WI  Wealth Index  (2):  CMWI22DT, CMWI31DT

  [ET] Ethiopia  —  57 files across 17 recode types
      AN  Antenatal Care Recode (SPA)  (2):  ETAN81DTSP, ETAN81DTSR
      AR  HIV Test Results Recode  (3):  ETAR51DT, ETAR61DT, ETAR71DT
      BR  Births Recode  (5):  ETBR41DT, ETBR51DT, ETBR61DT, ETBR71DT, ETBR81DT
      CR  Couples' Recode  (4):  ETCR41DT, ETCR51DT, ETCR61DT, ETCR71DT
      FC  Facility Inventory (SPA)  (2):  ETFC81DTSP, ETFC81DTSR
      FP  Family Planning Recode (SPA)  (2):  ETFP81DTSP, ETFP81DTSR
      GE  Geographic Data (GPS cluster coordinates)  (6):  ETGE42FL, ETGE52FL, ETGE61FL, ETGE71FL, ETGE81FL, ETGE81FLSR
      HR  Household Recode  (5):  ETHR41DT, ETHR51DT, ETHR61DT, ETHR71DT, ETHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  ETHW41DT, ETHW51DT
      IR  Individual Recode (Women)  (5):  ETIR41DT, ETIR51DT, ETIR61DT, ETIR71DT, ETIR81DT
      KR  Children's Recode  (5):  ETKR41DT, ETKR51DT, ETKR61DT, ETKR71DT, ETKR81DT
      MR  Men's Recode  (4):  ETMR41DT, ETMR51DT, ETMR61DT, ETMR71DT
      PR  Household Member Recode  (5):  ETPR41DT, ETPR51DT, ETPR61DT, ETPR71DT, ETPR81DT
      PV  Provider (SPA)  (2):  ETPV81DTSP, ETPV81DTSR
      SC  Sick Child Recode (SPA)  (2):  ETSC81DTSP, ETSC81DTSR
      SL  Staff / Provider Listing (SPA)  (2):  ETSL81DTSP, ETSL81DTSR
      WI  Wealth Index  (1):  ETWI41DT

  [GA] Gabon  —  28 files across 12 recode types
      AR  HIV Test Results Recode  (2):  GAAR61DT, GAAR71DT
      BR  Births Recode  (3):  GABR41DT, GABR61DT, GABR71DT
      CR  Couples' Recode  (3):  GACR41DT, GACR61DT, GACR71DT
      GE  Geographic Data (GPS cluster coordinates)  (2):  GAGE61FL, GAGE71FL
      HR  Household Recode  (3):  GAHR41DT, GAHR61DT, GAHR71DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (1):  GAHW41DT
      IR  Individual Recode (Women)  (3):  GAIR41DT, GAIR61DT, GAIR71DT
      KR  Children's Recode  (3):  GAKR41DT, GAKR61DT, GAKR71DT
      MR  Men's Recode  (3):  GAMR41DT, GAMR61DT, GAMR71DT
      PR  Household Member Recode  (3):  GAPR41DT, GAPR61DT, GAPR71DT
      SQ  Service Provision recode (SPA)  (1):  GASQ41DT
      WI  Wealth Index  (1):  GAWI41DT

  [GH] Ghana  —  88 files across 24 recode types
      AN  Antenatal Care Recode (SPA)  (1):  GHAN4IDTSP
      AR  HIV Test Results Recode  (2):  GHAR4ADT, GHAR71DT
      BQ  Biomarker Questionnaire  (1):  GHBQ7JDT
      BR  Births Recode  (7):  GHBR02DT, GHBR31DT, GHBR41DT, GHBR4BDT, GHBR5ADT, GHBR72DT, GHBR8CDT
      CR  Couples' Recode  (6):  GHCR31DT, GHCR41DT, GHCR4BDT, GHCR5ADT, GHCR71DT, GHCR8CDT
      FC  Facility Inventory (SPA)  (1):  GHFC4IDTSP
      FP  Family Planning Recode (SPA)  (1):  GHFP4IDTSP
      GE  Geographic Data (GPS cluster coordinates)  (9):  GHGE33FL, GHGE42FL, GHGE4BFL, GHGE5AFL, GHGE71FL, GHGE7AFL, GHGE7IFL, GHGE81FL, GHGE8AFL
      GR  Pregnancy and Postnatal Care Recode  (1):  GHGR8CDT
      HH  Household Raw  (3):  GHHH01DT, GHHH51DT, GHHH7JDT
      HR  Household Recode  (8):  GHHR31DT, GHHR41DT, GHHR4BDT, GHHR5ADT, GHHR72DT, GHHR7BDT, GHHR82DT, GHHR8CDT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (4):  GHHW02DT, GHHW31DT, GHHW41DT, GHHW4ADT
      IQ  Individual Raw (Women)  (2):  GHIQ51DT, GHIQ7JDT
      IR  Individual Recode (Women)  (9):  GHIR02DT, GHIR31DT, GHIR41DT, GHIR4BDT, GHIR5ADT, GHIR72DT, GHIR7BDT, GHIR82DT, GHIR8CDT
      KR  Children's Recode  (9):  GHKR01DT, GHKR31DT, GHKR41DT, GHKR4BDT, GHKR5ADT, GHKR72DT, GHKR7BDT, GHKR82DT, GHKR8CDT
      MR  Men's Recode  (6):  GHMR31DT, GHMR41DT, GHMR4BDT, GHMR5ADT, GHMR71DT, GHMR8CDT
      NR  Pregnancies Recode  (1):  GHNR8CDT
      OD  Other Data  (1):  GHOD51DT
      PR  Household Member Recode  (8):  GHPR31DT, GHPR41DT, GHPR4BDT, GHPR5ADT, GHPR72DT, GHPR7BDT, GHPR82DT, GHPR8CDT
      PV  Provider (SPA)  (1):  GHPV4IDTSP
      SC  Sick Child Recode (SPA)  (1):  GHSC4IDTSP
      SI  Safe Injection (SPA)  (1):  GHSI4IDTSP
      VA  Verbal Autopsy  (3):  GHVA51DT, GHVA5ADT, GHVA7IDT
      WI  Wealth Index  (2):  GHWI31DT, GHWI41DT

  [GM] Gambia  —  16 files across 9 recode types
      AR  HIV Test Results Recode  (1):  GMAR61DT
      BR  Births Recode  (2):  GMBR61DT, GMBR81DT
      CR  Couples' Recode  (2):  GMCR61DT, GMCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  GMGE81FL
      HR  Household Recode  (2):  GMHR61DT, GMHR81DT
      IR  Individual Recode (Women)  (2):  GMIR61DT, GMIR81DT
      KR  Children's Recode  (2):  GMKR61DT, GMKR81DT
      MR  Men's Recode  (2):  GMMR61DT, GMMR81DT
      PR  Household Member Recode  (2):  GMPR61DT, GMPR81DT

  [GN] Guinea  —  44 files across 12 recode types
      AR  HIV Test Results Recode  (3):  GNAR51DT, GNAR61DT, GNAR71DT
      BR  Births Recode  (4):  GNBR41DT, GNBR52DT, GNBR62DT, GNBR71DT
      CR  Couples' Recode  (4):  GNCR41DT, GNCR52DT, GNCR62DT, GNCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (5):  GNGE42FL, GNGE52FL, GNGE61FL, GNGE71FL, GNGE81FL
      HR  Household Recode  (5):  GNHR41DT, GNHR52DT, GNHR62DT, GNHR71DT, GNHR82DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  GNHW41DT, GNHW51DT
      IR  Individual Recode (Women)  (5):  GNIR41DT, GNIR52DT, GNIR62DT, GNIR71DT, GNIR82DT
      KR  Children's Recode  (5):  GNKR41DT, GNKR52DT, GNKR62DT, GNKR71DT, GNKR82DT
      MR  Men's Recode  (4):  GNMR41DT, GNMR52DT, GNMR62DT, GNMR71DT
      PR  Household Member Recode  (5):  GNPR41DT, GNPR53DT, GNPR62DT, GNPR71DT, GNPR82DT
      SQ  Service Provision recode (SPA)  (1):  GNSQ41DT
      WI  Wealth Index  (1):  GNWI41DT

  [KE] Kenya  —  123 files across 36 recode types
      AN  Antenatal Care Recode (SPA)  (5):  KEAN4ADTSP, KEAN5ADTSP, KEAN5BDTSR, KEAN6ADTSR, KEAN6BDTSP
      AR  HIV Test Results Recode  (2):  KEAR42DT, KEAR51DT
      AT  ART (SPA)  (2):  KEAT5ADTSP, KEAT5BDTSR
      BR  Births Recode  (7):  KEBR03DT, KEBR33DT, KEBR3ADT, KEBR42DT, KEBR52DT, KEBR72DT, KEBR8CDT
      CL  Client (SPA)  (1):  KECL5BDTSR
      CO  Country Specific (SPA)  (1):  KECO4ADTSP
      CR  Couples' Recode  (6):  KECR32DT, KECR3ADT, KECR42DT, KECR52DT, KECR72DT, KECR8CDT
      CS  Country Specific (SPA, alt)  (1):  KECS6BDTSP
      CT  Community Recode  (2):  KECT5ADTSP, KECT5BDTSR
      FC  Facility Inventory (SPA)  (5):  KEFC4ADTSP, KEFC5ADTSP, KEFC5BDTSR, KEFC6ADTSR, KEFC6BDTSP
      FP  Family Planning Recode (SPA)  (5):  KEFP4ADTSP, KEFP5ADTSP, KEFP5BDTSR, KEFP6ADTSR, KEFP6BDTSP
      GE  Geographic Data (GPS cluster coordinates)  (7):  KEGE43FL, KEGE52FL, KEGE6AFLSR, KEGE71FL, KEGE7AFL, KEGE81FL, KEGE8AFL
      GR  Pregnancy and Postnatal Care Recode  (1):  KEGR8CDT
      HH  Household Raw  (1):  KEHH01DT
      HR  Household Recode  (8):  KEHR33DT, KEHR3ADT, KEHR42DT, KEHR52DT, KEHR72DT, KEHR7ADT, KEHR81DT, KEHR8CDT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  KEHW33DT, KEHW3ADT, KEHW41DT
      IP  Inpatient/Outpatient (SPA)  (1):  KEIP5ADTSP
      IR  Individual Recode (Women)  (9):  KEIR03DT, KEIR33DT, KEIR3ADT, KEIR42DT, KEIR52DT, KEIR72DT, KEIR7ADT, KEIR81DT, KEIR8CDT
      KR  Children's Recode  (9):  KEKR01DT, KEKR31DT, KEKR3ADT, KEKR42DT, KEKR52DT, KEKR72DT, KEKR7ADT, KEKR81DT, KEKR8CDT
      LB  Labor & Delivery (SPA)  (1):  KELB5BDTSR
      LD  Labor & Delivery alt (SPA)  (2):  KELD6ADTSR, KELD6BDTSP
      MR  Men's Recode  (6):  KEMR32DT, KEMR3ADT, KEMR42DT, KEMR52DT, KEMR72DT, KEMR8CDT
      MS  Men's Raw  (1):  KEMS5BDTSR
      NR  Pregnancies Recode  (1):  KENR8CDT
      OI  Outpatient/Inpatient (SPA)  (1):  KEOI5BDTSR
      OP  Outpatient (SPA)  (1):  KEOP5ADTSP
      PH  Pharmacy (SPA)  (1):  KEPH5BDTSR
      PM  PMTCT (SPA)  (2):  KEPM5ADTSP, KEPM5BDTSR
      PR  Household Member Recode  (8):  KEPR33DT, KEPR3ADT, KEPR42DT, KEPR52DT, KEPR72DT, KEPR7ADT, KEPR81DT, KEPR8CDT
      PV  Provider (SPA)  (5):  KEPV4ADTSP, KEPV5ADTSP, KEPV5BDTSR, KEPV6ADTSR, KEPV6BDTSP
      SC  Sick Child Recode (SPA)  (5):  KESC4ADTSP, KESC5ADTSP, KESC5BDTSR, KESC6ADTSR, KESC6BDTSP
      SI  Safe Injection (SPA)  (5):  KESI4ADTSP, KESI5ADTSP, KESI5BDTSR, KESI6ADTSR, KESI6BDTSP
      SL  Staff / Provider Listing (SPA)  (3):  KESL5BDTSR, KESL6ADTSR, KESL6BDTSP
      SQ  Service Provision recode (SPA)  (1):  KESQ30DT
      TB  TB Data (SPA)  (2):  KETB5ADTSP, KETB5BDTSR
      WI  Wealth Index  (2):  KEWI31DT, KEWI3ADT

  [KM] Comoros  —  17 files across 10 recode types
      BR  Births Recode  (2):  KMBR32DT, KMBR61DT
      CR  Couples' Recode  (2):  KMCR31DT, KMCR61DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  KMGE61FL
      HR  Household Recode  (2):  KMHR32DT, KMHR61DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (1):  KMHW32DT
      IR  Individual Recode (Women)  (2):  KMIR32DT, KMIR61DT
      KR  Children's Recode  (2):  KMKR31DT, KMKR61DT
      MR  Men's Recode  (2):  KMMR31DT, KMMR61DT
      PR  Household Member Recode  (2):  KMPR32DT, KMPR61DT
      WI  Wealth Index  (1):  KMWI32DT

  [LB] Liberia  —  52 files across 10 recode types
      AR  HIV Test Results Recode  (2):  LBAR51DT, LBAR6ADT
      BR  Births Recode  (5):  LBBR01DT, LBBR51DT, LBBR5ADT, LBBR6ADT, LBBR7ADT
      CR  Couples' Recode  (3):  LBCR51DT, LBCR6ADT, LBCR7ADT
      GE  Geographic Data (GPS cluster coordinates)  (8):  LBGE03FL, LBGE52FL, LBGE5CFL, LBGE61FL, LBGE6AFL, LBGE71FL, LBGE7AFL, LBGE81FL
      HH  Household Raw  (1):  LBHH01DT
      HR  Household Recode  (7):  LBHR51DT, LBHR5ADT, LBHR61DT, LBHR6ADT, LBHR71DT, LBHR7ADT, LBHR81DT
      IR  Individual Recode (Women)  (8):  LBIR01DT, LBIR51DT, LBIR5ADT, LBIR61DT, LBIR6ADT, LBIR71DT, LBIR7ADT, LBIR81DT
      KR  Children's Recode  (8):  LBKR01DT, LBKR51DT, LBKR5ADT, LBKR61DT, LBKR6ADT, LBKR71DT, LBKR7ADT, LBKR81DT
      MR  Men's Recode  (3):  LBMR51DT, LBMR6ADT, LBMR7ADT
      PR  Household Member Recode  (7):  LBPR51DT, LBPR5ADT, LBPR61DT, LBPR6ADT, LBPR71DT, LBPR7ADT, LBPR81DT

  [LS] Lesotho  —  39 files across 13 recode types
      AR  HIV Test Results Recode  (3):  LSAR41DT, LSAR61DT, LSAR72DT
      BR  Births Recode  (4):  LSBR41DT, LSBR61DT, LSBR71DT, LSBR81DT
      CR  Couples' Recode  (4):  LSCR41DT, LSCR61DT, LSCR71DT, LSCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  LSGE42FL, LSGE62FL, LSGE71FL, LSGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  LSGR81DT
      HR  Household Recode  (4):  LSHR41DT, LSHR61DT, LSHR71DT, LSHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (1):  LSHW41DT
      IR  Individual Recode (Women)  (4):  LSIR41DT, LSIR61DT, LSIR71DT, LSIR81DT
      KR  Children's Recode  (4):  LSKR41DT, LSKR61DT, LSKR71DT, LSKR81DT
      MR  Men's Recode  (4):  LSMR41DT, LSMR61DT, LSMR71DT, LSMR81DT
      NR  Pregnancies Recode  (1):  LSNR81DT
      PR  Household Member Recode  (4):  LSPR41DT, LSPR61DT, LSPR71DT, LSPR81DT
      SR  Siblings Recode  (1):  LSSR81DT

  [MD] Madagascar  —  54 files across 11 recode types
      BR  Births Recode  (5):  MDBR21DT, MDBR31DT, MDBR42DT, MDBR51DT, MDBR81DT
      CR  Couples' Recode  (3):  MDCR42DT, MDCR51DT, MDCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (6):  MDGE32FL, MDGE53FL, MDGE61FL, MDGE6AFL, MDGE71FL, MDGE81FL
      HR  Household Recode  (8):  MDHR21DT, MDHR31DT, MDHR42DT, MDHR51DT, MDHR61DT, MDHR6ADT, MDHR71DT, MDHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  MDHW21DT, MDHW31DT, MDHW41DT
      IR  Individual Recode (Women)  (8):  MDIR21DT, MDIR31DT, MDIR42DT, MDIR51DT, MDIR61DT, MDIR6ADT, MDIR71DT, MDIR81DT
      KR  Children's Recode  (8):  MDKR21DT, MDKR31DT, MDKR42DT, MDKR51DT, MDKR61DT, MDKR6ADT, MDKR71DT, MDKR81DT
      MR  Men's Recode  (3):  MDMR42DT, MDMR51DT, MDMR81DT
      PR  Household Member Recode  (8):  MDPR21DT, MDPR31DT, MDPR42DT, MDPR51DT, MDPR61DT, MDPR6ADT, MDPR71DT, MDPR81DT
      SQ  Service Provision recode (SPA)  (1):  MDSQ21DT
      WI  Wealth Index  (1):  MDWI31DT

  [ML] Mali  —  78 files across 17 recode types
      AR  HIV Test Results Recode  (2):  MLAR51DT, MLAR6ADT
      BR  Births Recode  (7):  MLBR01DT, MLBR32DT, MLBR41DT, MLBR53DT, MLBR6ADT, MLBR7ADT, MLBR8ADT
      CR  Couples' Recode  (6):  MLCR31DT, MLCR41DT, MLCR53DT, MLCR6ADT, MLCR7ADT, MLCR8ADT
      GE  Geographic Data (GPS cluster coordinates)  (9):  MLGE33FL, MLGE42FL, MLGE52FL, MLGE63FL, MLGE6BFL, MLGE71FL, MLGE7AFL, MLGE81FL, MLGE8AFL
      GR  Pregnancy and Postnatal Care Recode  (1):  MLGR8ADT
      HH  Household Raw  (1):  MLHH01DT
      HR  Household Recode  (9):  MLHR32DT, MLHR41DT, MLHR53DT, MLHR61DT, MLHR6ADT, MLHR72DT, MLHR7ADT, MLHR83DT, MLHR8ADT
      HT  Health Information System (SPA)  (1):  MLHT41DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  MLHW01DT, MLHW32DT, MLHW41DT
      IR  Individual Recode (Women)  (9):  MLIR01DT, MLIR32DT, MLIR41DT, MLIR53DT, MLIR6ADT, MLIR72DT, MLIR7ADT, MLIR83DT, MLIR8ADT
      KR  Children's Recode  (9):  MLKR01DT, MLKR31DT, MLKR41DT, MLKR53DT, MLKR6ADT, MLKR72DT, MLKR7ADT, MLKR83DT, MLKR8ADT
      ML  Malaria (SPA)  (1):  MLML01DT
      MR  Men's Recode  (6):  MLMR31DT, MLMR41DT, MLMR53DT, MLMR6ADT, MLMR7ADT, MLMR8ADT
      NR  Pregnancies Recode  (1):  MLNR8ADT
      PR  Household Member Recode  (9):  MLPR32DT, MLPR41DT, MLPR53DT, MLPR61DT, MLPR6ADT, MLPR72DT, MLPR7ADT, MLPR83DT, MLPR8ADT
      SQ  Service Provision recode (SPA)  (2):  MLSQ31DT, MLSQ42DT
      WI  Wealth Index  (2):  MLWI32DT, MLWI42DT

  [MR] Mauritania  —  8 files across 8 recode types
      BR  Births Recode  (1):  MRBR71DT
      CR  Couples' Recode  (1):  MRCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  MRGE71FL
      HR  Household Recode  (1):  MRHR71DT
      IR  Individual Recode (Women)  (1):  MRIR71DT
      KR  Children's Recode  (1):  MRKR71DT
      MR  Men's Recode  (1):  MRMR71DT
      PR  Household Member Recode  (1):  MRPR71DT

  [MW] Malawi  —  92 files across 25 recode types
      AN  Antenatal Care Recode (SPA)  (2):  MWAN6IDTSR, MWAN6KDTSP
      AR  HIV Test Results Recode  (3):  MWAR4ADT, MWAR61DT, MWAR7ADT
      BR  Births Recode  (6):  MWBR22DT, MWBR41DT, MWBR4EDT, MWBR61DT, MWBR7ADT, MWBR81DT
      CR  Couples' Recode  (6):  MWCR21DT, MWCR41DT, MWCR4EDT, MWCR61DT, MWCR7ADT, MWCR81DT
      FC  Facility Inventory (SPA)  (2):  MWFC6JDTSR, MWFC6KDTSP
      FP  Family Planning Recode (SPA)  (2):  MWFP6IDTSR, MWFP6KDTSP
      GE  Geographic Data (GPS cluster coordinates)  (9):  MWGE43FL, MWGE4BFL, MWGE62FL, MWGE6AFL, MWGE6IFLSR, MWGE71FL, MWGE7AFL, MWGE7IFL, MWGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  MWGR81DT
      HH  Household Raw  (1):  MWHH34DT
      HR  Household Recode  (9):  MWHR22DT, MWHR41DT, MWHR4EDT, MWHR61DT, MWHR6ADT, MWHR72DT, MWHR7ADT, MWHR7IDT, MWHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  MWHW22DT, MWHW41DT, MWHW4CDT
      IQ  Individual Raw (Women)  (1):  MWIQ34DT
      IR  Individual Recode (Women)  (9):  MWIR22DT, MWIR41DT, MWIR4EDT, MWIR61DT, MWIR6ADT, MWIR72DT, MWIR7ADT, MWIR7IDT, MWIR81DT
      KR  Children's Recode  (9):  MWKR21DT, MWKR41DT, MWKR4EDT, MWKR61DT, MWKR6ADT, MWKR72DT, MWKR7ADT, MWKR7IDT, MWKR81DT
      LD  Labor & Delivery alt (SPA)  (2):  MWLD6IDTSR, MWLD6KDTSP
      ML  Malaria (SPA)  (1):  MWML34DT
      MR  Men's Recode  (6):  MWMR21DT, MWMR41DT, MWMR4EDT, MWMR61DT, MWMR7ADT, MWMR81DT
      NR  Pregnancies Recode  (1):  MWNR81DT
      PR  Household Member Recode  (9):  MWPR22DT, MWPR41DT, MWPR4EDT, MWPR61DT, MWPR6ADT, MWPR72DT, MWPR7ADT, MWPR7IDT, MWPR81DT
      PV  Provider (SPA)  (2):  MWPV6IDTSR, MWPV6KDTSP
      SC  Sick Child Recode (SPA)  (2):  MWSC6IDTSR, MWSC6KDTSP
      SL  Staff / Provider Listing (SPA)  (2):  MWSL6IDTSR, MWSL6KDTSP
      SQ  Service Provision recode (SPA)  (1):  MWSQ26DT
      SR  Siblings Recode  (1):  MWSR81DT
      WI  Wealth Index  (2):  MWWI22DT, MWWI42DT

  [MZ] Mozambique  —  57 files across 16 recode types
      AI  Accidents/Injuries Recode (SPA)  (1):  MZAI81DT
      AR  HIV Test Results Recode  (2):  MZAR51DT, MZAR72DT
      BR  Births Recode  (5):  MZBR31DT, MZBR41DT, MZBR62DT, MZBR71DT, MZBR81DT
      CR  Couples' Recode  (5):  MZCR31DT, MZCR41DT, MZCR62DT, MZCR71DT, MZCR81DT
      GE  Geographic Data (GPS cluster coordinates)  (5):  MZGE52FL, MZGE61FL, MZGE71FL, MZGE7AFL, MZGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  MZGR81DT
      HR  Household Recode  (7):  MZHR31DT, MZHR41DT, MZHR51DT, MZHR62DT, MZHR71DT, MZHR7ADT, MZHR81DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  MZHW31DT, MZHW41DT
      IR  Individual Recode (Women)  (7):  MZIR31DT, MZIR41DT, MZIR51DT, MZIR62DT, MZIR71DT, MZIR7ADT, MZIR81DT
      KR  Children's Recode  (6):  MZKR31DT, MZKR41DT, MZKR62DT, MZKR71DT, MZKR7ADT, MZKR81DT
      MR  Men's Recode  (5):  MZMR31DT, MZMR41DT, MZMR62DT, MZMR71DT, MZMR81DT
      NR  Pregnancies Recode  (1):  MZNR81DT
      OD  Other Data  (1):  MZOD51DT
      PR  Household Member Recode  (7):  MZPR31DT, MZPR41DT, MZPR51DT, MZPR62DT, MZPR71DT, MZPR7ADT, MZPR81DT
      SR  Siblings Recode  (1):  MZSR81DT
      WI  Wealth Index  (1):  MZWI31DT

  [NG] Nigeria  —  69 files across 14 recode types
      BR  Births Recode  (7):  NGBR21DT, NGBR4BDT, NGBR53DT, NGBR61DT, NGBR6ADT, NGBR7BDT, NGBR8BDT
      CR  Couples' Recode  (5):  NGCR4ADT, NGCR53DT, NGCR6ADT, NGCR7ADT, NGCR8BDT
      GE  Geographic Data (GPS cluster coordinates)  (9):  NGGE23FL, NGGE4BFL, NGGE52FL, NGGE61FL, NGGE6AFL, NGGE71FL, NGGE7BFL, NGGE81FL, NGGE8AFL
      GR  Pregnancy and Postnatal Care Recode  (1):  NGGR8BDT
      HR  Household Recode  (9):  NGHR21DT, NGHR4BDT, NGHR53DT, NGHR61DT, NGHR6ADT, NGHR71DT, NGHR7BDT, NGHR81DT, NGHR8BDT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  NGHW21DT, NGHW4BDT
      IR  Individual Recode (Women)  (9):  NGIR21DT, NGIR4BDT, NGIR53DT, NGIR61DT, NGIR6ADT, NGIR71DT, NGIR7BDT, NGIR81DT, NGIR8BDT
      KR  Children's Recode  (9):  NGKR21DT, NGKR4BDT, NGKR53DT, NGKR61DT, NGKR6ADT, NGKR71DT, NGKR7BDT, NGKR81DT, NGKR8BDT
      MR  Men's Recode  (5):  NGMR4ADT, NGMR52DT, NGMR6ADT, NGMR7ADT, NGMR8BDT
      NR  Pregnancies Recode  (1):  NGNR8BDT
      PR  Household Member Recode  (9):  NGPR21DT, NGPR4CDT, NGPR53DT, NGPR61DT, NGPR6ADT, NGPR71DT, NGPR7BDT, NGPR81DT, NGPR8BDT
      SQ  Service Provision recode (SPA)  (1):  NGSQ23DT
      SR  Siblings Recode  (1):  NGSR8BDT
      WI  Wealth Index  (1):  NGWI21DT

  [NI] Niger  —  44 files across 12 recode types
      AR  HIV Test Results Recode  (2):  NIAR51DT, NIAR61DT
      BR  Births Recode  (4):  NIBR22DT, NIBR31DT, NIBR51DT, NIBR61DT
      CR  Couples' Recode  (4):  NICR21DT, NICR31DT, NICR51DT, NICR61DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  NIGE23FL, NIGE32FL, NIGE61FL, NIGE81FL
      HR  Household Recode  (5):  NIHR22DT, NIHR31DT, NIHR51DT, NIHR61DT, NIHR82DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  NIHW22DT, NIHW31DT, NIHW51DT
      IR  Individual Recode (Women)  (5):  NIIR22DT, NIIR31DT, NIIR51DT, NIIR61DT, NIIR82DT
      KR  Children's Recode  (5):  NIKR21DT, NIKR31DT, NIKR51DT, NIKR61DT, NIKR82DT
      MR  Men's Recode  (4):  NIMR21DT, NIMR31DT, NIMR51DT, NIMR61DT
      PR  Household Member Recode  (5):  NIPR22DT, NIPR31DT, NIPR51DT, NIPR61DT, NIPR82DT
      SQ  Service Provision recode (SPA)  (2):  NISQ21DT, NISQ31DT
      WI  Wealth Index  (1):  NIWI31DT

  [NM] Namibia  —  47 files across 17 recode types
      AN  Antenatal Care Recode (SPA)  (2):  NMAN6ADTSP, NMAN6ADTSR
      AR  HIV Test Results Recode  (1):  NMAR61DT
      BR  Births Recode  (4):  NMBR21DT, NMBR41DT, NMBR51DT, NMBR61DT
      CR  Couples' Recode  (3):  NMCR41DT, NMCR51DT, NMCR61DT
      FC  Facility Inventory (SPA)  (2):  NMFC6ADTSP, NMFC6ADTSR
      FP  Family Planning Recode (SPA)  (2):  NMFP6ADTSP, NMFP6ADTSR
      GE  Geographic Data (GPS cluster coordinates)  (4):  NMGE42FL, NMGE53FL, NMGE61FL, NMGE6AFLSR
      HR  Household Recode  (4):  NMHR21DT, NMHR41DT, NMHR51DT, NMHR61DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  NMHW21DT, NMHW41DT
      IR  Individual Recode (Women)  (4):  NMIR21DT, NMIR41DT, NMIR51DT, NMIR61DT
      KR  Children's Recode  (4):  NMKR21DT, NMKR41DT, NMKR51DT, NMKR61DT
      MR  Men's Recode  (3):  NMMR41DT, NMMR51DT, NMMR61DT
      PR  Household Member Recode  (4):  NMPR21DT, NMPR41DT, NMPR52DT, NMPR61DT
      PV  Provider (SPA)  (2):  NMPV6ADTSP, NMPV6ADTSR
      SC  Sick Child Recode (SPA)  (2):  NMSC6ADTSP, NMSC6ADTSR
      SL  Staff / Provider Listing (SPA)  (2):  NMSL6ADTSP, NMSL6ADTSR
      WI  Wealth Index  (2):  NMWI21DT, NMWI41DT

  [RW] Rwanda  —  111 files across 33 recode types
      AN  Antenatal Care Recode (SPA)  (2):  RWAN5IDTSP, RWAN5JDTSR
      AR  HIV Test Results Recode  (4):  RWAR51DT, RWAR61DT, RWAR71DT, RWAR81DT
      AT  ART (SPA)  (2):  RWAT5IDTSP, RWAT5JDTSR
      BR  Births Recode  (7):  RWBR21DT, RWBR41DT, RWBR53DT, RWBR5ADT, RWBR61DT, RWBR70DT, RWBR81DT
      CL  Client (SPA)  (1):  RWCL5JDTSR
      CN  Consultations (SPA)  (1):  RWCN4ADTSP
      CR  Couples' Recode  (6):  RWCR21DT, RWCR41DT, RWCR53DT, RWCR61DT, RWCR70DT, RWCR81DT
      CT  Community Recode  (2):  RWCT5IDTSP, RWCT5JDTSR
      FC  Facility Inventory (SPA)  (2):  RWFC5IDTSP, RWFC5JDTSR
      FP  Family Planning Recode (SPA)  (2):  RWFP5IDTSP, RWFP5JDTSR
      GE  Geographic Data (GPS cluster coordinates)  (6):  RWGE54FL, RWGE5BFL, RWGE61FL, RWGE72FL, RWGE81FL, RWGE8AFL
      HH  Household Raw  (1):  RWHH6ADT
      HR  Household Recode  (10):  RWHR21DT, RWHR41DT, RWHR53DT, RWHR5ADT, RWHR61DT, RWHR6IDT, RWHR70DT, RWHR7ADT, RWHR81DT, RWHR8ADT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  RWHW21DT, RWHW41DT, RWHW52DT
      IN  Inpatient (SPA)  (1):  RWIN4ADTSP
      IP  Inpatient/Outpatient (SPA)  (1):  RWIP5IDTSP
      IQ  Individual Raw (Women)  (1):  RWIQ6ADT
      IR  Individual Recode (Women)  (10):  RWIR21DT, RWIR41DT, RWIR53DT, RWIR5ADT, RWIR61DT, RWIR6IDT, RWIR70DT, RWIR7ADT, RWIR81DT, RWIR8ADT
      KR  Children's Recode  (10):  RWKR21DT, RWKR41DT, RWKR53DT, RWKR5ADT, RWKR61DT, RWKR6IDT, RWKR70DT, RWKR7ADT, RWKR81DT, RWKR8ADT
      LB  Labor & Delivery (SPA)  (2):  RWLB5IDTSP, RWLB5JDTSR
      MR  Men's Recode  (7):  RWMR21DT, RWMR41DT, RWMR53DT, RWMR5ADT, RWMR61DT, RWMR70DT, RWMR81DT
      MS  Men's Raw  (2):  RWMS5IDTSP, RWMS5JDTSR
      OI  Outpatient/Inpatient (SPA)  (1):  RWOI5JDTSR
      OP  Outpatient (SPA)  (1):  RWOP5IDTSP
      PH  Pharmacy (SPA)  (2):  RWPH5IDTSP, RWPH5JDTSR
      PM  PMTCT (SPA)  (2):  RWPM5IDTSP, RWPM5JDTSR
      PR  Household Member Recode  (10):  RWPR21DT, RWPR41DT, RWPR53DT, RWPR5ADT, RWPR61DT, RWPR6IDT, RWPR70DT, RWPR7ADT, RWPR81DT, RWPR8ADT
      PV  Provider (SPA)  (3):  RWPV4ADTSP, RWPV5IDTSP, RWPV5JDTSR
      SC  Sick Child Recode (SPA)  (2):  RWSC5IDTSP, RWSC5JDTSR
      SI  Safe Injection (SPA)  (2):  RWSI5IDTSP, RWSI5JDTSR
      SL  Staff / Provider Listing (SPA)  (1):  RWSL5JDTSR
      TB  TB Data (SPA)  (2):  RWTB5IDTSP, RWTB5JDTSR
      WI  Wealth Index  (2):  RWWI21DT, RWWI42DT

  [SL] Sierra Leone  —  32 files across 9 recode types
      AR  HIV Test Results Recode  (3):  SLAR51DT, SLAR61DT, SLAR7ADT
      BR  Births Recode  (3):  SLBR51DT, SLBR61DT, SLBR7ADT
      CR  Couples' Recode  (3):  SLCR51DT, SLCR61DT, SLCR7ADT
      GE  Geographic Data (GPS cluster coordinates)  (4):  SLGE53FL, SLGE61FL, SLGE71FL, SLGE7AFL
      HR  Household Recode  (4):  SLHR51DT, SLHR61DT, SLHR73DT, SLHR7ADT
      IR  Individual Recode (Women)  (4):  SLIR51DT, SLIR61DT, SLIR73DT, SLIR7ADT
      KR  Children's Recode  (4):  SLKR51DT, SLKR61DT, SLKR73DT, SLKR7ADT
      MR  Men's Recode  (3):  SLMR51DT, SLMR61DT, SLMR7ADT
      PR  Household Member Recode  (4):  SLPR51DT, SLPR61DT, SLPR73DT, SLPR7ADT

  [SN] Senegal  —  172 files across 24 recode types
      AN  Antenatal Care Recode (SPA)  (3):  SNAN72DTSP, SNAN7QDTSP, SNAN81DTSP
      AR  HIV Test Results Recode  (3):  SNAR4ADT, SNAR61DT, SNAR7RDT
      BR  Births Recode  (14):  SNBR02DT, SNBR21DT, SNBR32DT, SNBR4ADT, SNBR5ADT, SNBR61DT, SNBR6DDT, SNBR71DT, SNBR7ADT, SNBR7IDT, SNBR7ZDT, SNBR81DT, SNBR8BDT, SNBR8SDT
      CR  Couples' Recode  (11):  SNCR21DT, SNCR31DT, SNCR4ADT, SNCR61DT, SNCR71DT, SNCR7ADT, SNCR7IDT, SNCR7ZDT, SNCR81DT, SNCR8BDT, SNCR8SDT
      FC  Facility Inventory (SPA)  (8):  SNFC6IDTSP, SNFC6IDTSR, SNFC72DTSP, SNFC7ADTSP, SNFC7QDTSP, SNFC7ZDTSP, SNFC81DTSP, SNFC8ADTSP
      FP  Family Planning Recode (SPA)  (5):  SNFP6IDTSP, SNFP6IDTSR, SNFP7ADTSP, SNFP7ZDTSP, SNFP8ADTSP
      GE  Geographic Data (GPS cluster coordinates)  (19):  SNGE23FL, SNGE32FL, SNGE4BFL, SNGE5AFL, SNGE61FL, SNGE6AFL, SNGE6IFLSR, SNGE71FL, SNGE71FLSR, SNGE7AFL, SNGE7AFLSR, SNGE7IFL, SNGE7IFLSR, SNGE7RFL, SNGE7RFLSR, SNGE81FL, SNGE8BFL, SNGE8IFL, SNGE8RFL
      GR  Pregnancy and Postnatal Care Recode  (1):  SNGR8SDT
      HH  Household Raw  (2):  SNHH01DT, SNHH41DT
      HR  Household Recode  (15):  SNHR21DT, SNHR32DT, SNHR4ADT, SNHR51DT, SNHR5ADT, SNHR61DT, SNHR6DDT, SNHR71DT, SNHR7ADT, SNHR7IDT, SNHR7ZDT, SNHR81DT, SNHR8BDT, SNHR8IDT, SNHR8SDT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  SNHW02DT, SNHW21DT, SNHW4ADT
      IQ  Individual Raw (Women)  (1):  SNIQ41DT
      IR  Individual Recode (Women)  (16):  SNIR02DT, SNIR21DT, SNIR32DT, SNIR4ADT, SNIR51DT, SNIR5ADT, SNIR61DT, SNIR6DDT, SNIR71DT, SNIR7ADT, SNIR7IDT, SNIR7ZDT, SNIR81DT, SNIR8BDT, SNIR8IDT, SNIR8SDT
      KR  Children's Recode  (16):  SNKR01DT, SNKR21DT, SNKR32DT, SNKR4ADT, SNKR51DT, SNKR5ADT, SNKR61DT, SNKR6DDT, SNKR71DT, SNKR7ADT, SNKR7IDT, SNKR7ZDT, SNKR81DT, SNKR8BDT, SNKR8IDT, SNKR8SDT
      ML  Malaria (SPA)  (1):  SNML41DT
      MR  Men's Recode  (11):  SNMR21DT, SNMR31DT, SNMR4ADT, SNMR61DT, SNMR71DT, SNMR7ADT, SNMR7IDT, SNMR7ZDT, SNMR81DT, SNMR8BDT, SNMR8SDT
      NR  Pregnancies Recode  (1):  SNNR8SDT
      PR  Household Member Recode  (15):  SNPR21DT, SNPR32DT, SNPR4ADT, SNPR51DT, SNPR5ADT, SNPR61DT, SNPR6DDT, SNPR71DT, SNPR7ADT, SNPR7IDT, SNPR7ZDT, SNPR81DT, SNPR8BDT, SNPR8IDT, SNPR8SDT
      PV  Provider (SPA)  (8):  SNPV6IDTSP, SNPV6IDTSR, SNPV72DTSP, SNPV7ADTSP, SNPV7QDTSP, SNPV7ZDTSP, SNPV81DTSP, SNPV8ADTSP
      SC  Sick Child Recode (SPA)  (8):  SNSC6IDTSP, SNSC6IDTSR, SNSC72DTSP, SNSC7ADTSP, SNSC7QDTSP, SNSC7ZDTSP, SNSC81DTSP, SNSC8ADTSP
      SL  Staff / Provider Listing (SPA)  (8):  SNSL6IDTSP, SNSL6IDTSR, SNSL72DTSP, SNSL7ADTSP, SNSL7QDTSP, SNSL7ZDTSP, SNSL81DTSP, SNSL8ADTSP
      SQ  Service Provision recode (SPA)  (1):  SNSQ22DT
      SR  Siblings Recode  (1):  SNSR8SDT
      WI  Wealth Index  (1):  SNWI32DT

  [SZ] Eswatini (Swaziland)  —  9 files across 9 recode types
      AR  HIV Test Results Recode  (1):  SZAR51DT
      BR  Births Recode  (1):  SZBR51DT
      CR  Couples' Recode  (1):  SZCR51DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  SZGE53FL
      HR  Household Recode  (1):  SZHR51DT
      IR  Individual Recode (Women)  (1):  SZIR51DT
      KR  Children's Recode  (1):  SZKR51DT
      MR  Men's Recode  (1):  SZMR51DT
      PR  Household Member Recode  (1):  SZPR52DT

  [TD] Chad  —  28 files across 12 recode types
      AR  HIV Test Results Recode  (1):  TDAR71DT
      BR  Births Recode  (3):  TDBR31DT, TDBR41DT, TDBR71DT
      CR  Couples' Recode  (3):  TDCR31DT, TDCR41DT, TDCR71DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  TDGE71FL
      HR  Household Recode  (3):  TDHR31DT, TDHR41DT, TDHR71DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  TDHW31DT, TDHW41DT
      IR  Individual Recode (Women)  (3):  TDIR31DT, TDIR41DT, TDIR71DT
      KR  Children's Recode  (3):  TDKR31DT, TDKR41DT, TDKR71DT
      MR  Men's Recode  (3):  TDMR31DT, TDMR41DT, TDMR71DT
      PR  Household Member Recode  (3):  TDPR31DT, TDPR41DT, TDPR71DT
      SQ  Service Provision recode (SPA)  (2):  TDSQ32DT, TDSQ41DT
      WI  Wealth Index  (1):  TDWI31DT

  [TG] Togo  —  31 files across 13 recode types
      AR  HIV Test Results Recode  (1):  TGAR61DT
      BR  Births Recode  (3):  TGBR01DT, TGBR31DT, TGBR61DT
      CR  Couples' Recode  (2):  TGCR31DT, TGCR61DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  TGGE03FL, TGGE32FL, TGGE62FL, TGGE71FL
      HH  Household Raw  (1):  TGHH01DT
      HR  Household Recode  (3):  TGHR31DT, TGHR61DT, TGHR71DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (2):  TGHW01DT, TGHW31DT
      IR  Individual Recode (Women)  (4):  TGIR01DT, TGIR31DT, TGIR61DT, TGIR71DT
      KR  Children's Recode  (4):  TGKR01DT, TGKR31DT, TGKR61DT, TGKR71DT
      MR  Men's Recode  (2):  TGMR31DT, TGMR61DT
      PR  Household Member Recode  (3):  TGPR31DT, TGPR61DT, TGPR71DT
      SQ  Service Provision recode (SPA)  (1):  TGSQ01DT
      WI  Wealth Index  (1):  TGWI31DT

  [TZ] Tanzania  —  136 files across 36 recode types
      AN  Antenatal Care Recode (SPA)  (4):  TZAN5ADTSP, TZAN5ADTSR, TZAN71DTSP, TZAN71DTSR
      AR  HIV Test Results Recode  (3):  TZAR4ADT, TZAR51DT, TZAR6ADT
      AT  ART (SPA)  (2):  TZAT5ADTSP, TZAT5ADTSR
      BR  Births Recode  (9):  TZBR21DT, TZBR3ADT, TZBR41DT, TZBR4IDT, TZBR51DT, TZBR63DT, TZBR6ADT, TZBR7BDT, TZBR82DT
      CL  Client (SPA)  (2):  TZCL5ADTSP, TZCL5ADTSR
      CR  Couples' Recode  (7):  TZCR21DT, TZCR3ADT, TZCR41DT, TZCR4IDT, TZCR63DT, TZCR7BDT, TZCR82DT
      CT  Community Recode  (2):  TZCT5ADTSP, TZCT5ADTSR
      FC  Facility Inventory (SPA)  (4):  TZFC5ADTSP, TZFC5ADTSR, TZFC71DTSP, TZFC71DTSR
      FP  Family Planning Recode (SPA)  (4):  TZFP5ADTSP, TZFP5ADTSR, TZFP71DTSP, TZFP71DTSR
      GE  Geographic Data (GPS cluster coordinates)  (9):  TZGE43FL, TZGE4CFL, TZGE52FL, TZGE61FL, TZGE6AFL, TZGE71FLSR, TZGE7AFL, TZGE7IFL, TZGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  TZGR82DT
      HH  Household Raw  (1):  TZHH31DT
      HR  Household Recode  (11):  TZHR21DT, TZHR3ADT, TZHR41DT, TZHR4ADT, TZHR4IDT, TZHR51DT, TZHR63DT, TZHR6ADT, TZHR7BDT, TZHR7IDT, TZHR82DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (4):  TZHW21DT, TZHW3ADT, TZHW41DT, TZHW4IDT
      IP  Inpatient/Outpatient (SPA)  (1):  TZIP5ADTSP
      IQ  Individual Raw (Women)  (1):  TZIQ31DT
      IR  Individual Recode (Women)  (11):  TZIR21DT, TZIR3ADT, TZIR41DT, TZIR4ADT, TZIR4IDT, TZIR51DT, TZIR63DT, TZIR6ADT, TZIR7BDT, TZIR7IDT, TZIR82DT
      KR  Children's Recode  (10):  TZKR21DT, TZKR3ADT, TZKR41DT, TZKR4IDT, TZKR51DT, TZKR63DT, TZKR6ADT, TZKR7BDT, TZKR7IDT, TZKR82DT
      LB  Labor & Delivery (SPA)  (2):  TZLB5ADTSP, TZLB5ADTSR
      ML  Malaria (SPA)  (1):  TZML31DT
      MR  Men's Recode  (7):  TZMR21DT, TZMR3ADT, TZMR41DT, TZMR4IDT, TZMR61DT, TZMR7BDT, TZMR82DT
      MS  Men's Raw  (2):  TZMS5ADTSP, TZMS5ADTSR
      NR  Pregnancies Recode  (1):  TZNR82DT
      OI  Outpatient/Inpatient (SPA)  (1):  TZOI5ADTSR
      OP  Outpatient (SPA)  (1):  TZOP5ADTSP
      PH  Pharmacy (SPA)  (2):  TZPH5ADTSP, TZPH5ADTSR
      PM  PMTCT (SPA)  (2):  TZPM5ADTSP, TZPM5ADTSR
      PR  Household Member Recode  (11):  TZPR21DT, TZPR3ADT, TZPR41DT, TZPR4ADT, TZPR4IDT, TZPR51DT, TZPR63DT, TZPR6ADT, TZPR7BDT, TZPR7IDT, TZPR82DT
      PV  Provider (SPA)  (4):  TZPV5ADTSP, TZPV5ADTSR, TZPV71DTSP, TZPV71DTSR
      SC  Sick Child Recode (SPA)  (4):  TZSC5ADTSP, TZSC5ADTSR, TZSC71DTSP, TZSC71DTSR
      SI  Safe Injection (SPA)  (2):  TZSI5ADTSP, TZSI5ADTSR
      SL  Staff / Provider Listing (SPA)  (4):  TZSL5ADTSP, TZSL5ADTSR, TZSL71DTSP, TZSL71DTSR
      SQ  Service Provision recode (SPA)  (1):  TZSQ21DT
      SR  Siblings Recode  (1):  TZSR82DT
      TB  TB Data (SPA)  (2):  TZTB5ADTSP, TZTB5ADTSR
      WI  Wealth Index  (2):  TZWI3ADT, TZWI41DT

  [UG] Uganda  —  113 files across 35 recode types
      AN  Antenatal Care Recode (SPA)  (2):  UGAN5RDTSP, UGAN5SDTSR
      AR  HIV Test Results Recode  (1):  UGAR6ADT
      AT  ART (SPA)  (2):  UGAT5RDTSP, UGAT5SDTSR
      BR  Births Recode  (7):  UGBR01DT, UGBR33DT, UGBR41DT, UGBR52DT, UGBR5ADT, UGBR61DT, UGBR7BDT
      CL  Client (SPA)  (1):  UGCL5SDTSR
      CR  Couples' Recode  (5):  UGCR33DT, UGCR41DT, UGCR52DT, UGCR61DT, UGCR7BDT
      CT  Community Recode  (2):  UGCT5RDTSP, UGCT5SDTSR
      FC  Facility Inventory (SPA)  (2):  UGFC5RDTSP, UGFC5SDTSR
      FP  Family Planning Recode (SPA)  (2):  UGFP5RDTSP, UGFP5SDTSR
      GE  Geographic Data (GPS cluster coordinates)  (9):  UGGE43FL, UGGE53FL, UGGE5AFL, UGGE61FL, UGGE6AFL, UGGE71FL, UGGE7AFL, UGGE7IFL, UGGE91FL
      HH  Household Raw  (2):  UGHH01DT, UGHH3ADT
      HR  Household Recode  (10):  UGHR33DT, UGHR41DT, UGHR52DT, UGHR5ADT, UGHR61DT, UGHR6ADT, UGHR72DT, UGHR7BDT, UGHR7IDT, UGHR91DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  UGHW01DT, UGHW33DT, UGHW41DT
      IN  Inpatient (SPA)  (2):  UGIN5RDTSP, UGIN5SDTSR
      IP  Inpatient/Outpatient (SPA)  (1):  UGIP5RDTSP
      IQ  Individual Raw (Women)  (1):  UGIQ3BDT
      IR  Individual Recode (Women)  (11):  UGIR01DT, UGIR33DT, UGIR41DT, UGIR52DT, UGIR5ADT, UGIR61DT, UGIR6ADT, UGIR72DT, UGIR7BDT, UGIR7IDT, UGIR91DT
      KR  Children's Recode  (10):  UGKR01DT, UGKR33DT, UGKR41DT, UGKR52DT, UGKR5ADT, UGKR61DT, UGKR72DT, UGKR7BDT, UGKR7IDT, UGKR91DT
      LB  Labor & Delivery (SPA)  (2):  UGLB5RDTSP, UGLB5SDTSR
      ML  Malaria (SPA)  (1):  UGML3ADT
      MR  Men's Recode  (5):  UGMR33DT, UGMR41DT, UGMR52DT, UGMR61DT, UGMR7BDT
      MS  Men's Raw  (2):  UGMS5RDTSP, UGMS5SDTSR
      OD  Other Data  (1):  UGOD6ADT
      OI  Outpatient/Inpatient (SPA)  (1):  UGOI5SDTSR
      OP  Outpatient (SPA)  (1):  UGOP5RDTSP
      PH  Pharmacy (SPA)  (2):  UGPH5RDTSP, UGPH5SDTSR
      PM  PMTCT (SPA)  (2):  UGPM5RDTSP, UGPM5SDTSR
      PR  Household Member Recode  (10):  UGPR33DT, UGPR41DT, UGPR52DT, UGPR5ADT, UGPR61DT, UGPR6ADT, UGPR72DT, UGPR7BDT, UGPR7IDT, UGPR91DT
      PV  Provider (SPA)  (2):  UGPV5RDTSP, UGPV5SDTSR
      SC  Sick Child Recode (SPA)  (2):  UGSC5RDTSP, UGSC5SDTSR
      SI  Safe Injection (SPA)  (2):  UGSI5RDTSP, UGSI5SDTSR
      SL  Staff / Provider Listing (SPA)  (1):  UGSL5SDTSR
      SQ  Service Provision recode (SPA)  (2):  UGSQ01DT, UGSQ33DT
      TB  TB Data (SPA)  (2):  UGTB5RDTSP, UGTB5SDTSR
      WI  Wealth Index  (2):  UGWI33DT, UGWI41DT

  [ZA] South Africa  —  16 files across 11 recode types
      AR  HIV Test Results Recode  (1):  ZAAR71DT
      BR  Births Recode  (2):  ZABR31DT, ZABR71DT
      CR  Couples' Recode  (1):  ZACR71DT
      GE  Geographic Data (GPS cluster coordinates)  (1):  ZAGE71FL
      HR  Household Recode  (2):  ZAHR31DT, ZAHR71DT
      IR  Individual Recode (Women)  (2):  ZAIR31DT, ZAIR71DT
      KR  Children's Recode  (2):  ZAKR31DT, ZAKR71DT
      MR  Men's Recode  (1):  ZAMR71DT
      OD  Other Data  (1):  ZAOD71DT
      PR  Household Member Recode  (2):  ZAPR31DT, ZAPR71DT
      WI  Wealth Index  (1):  ZAWI31DT

  [ZM] Zambia  —  83 files across 29 recode types
      AR  HIV Test Results Recode  (4):  ZMAR51DT, ZMAR63DT, ZMAR71DT, ZMAR81DT
      AT  ART (SPA)  (1):  ZMAT5ADTSR
      BR  Births Recode  (7):  ZMBR21DT, ZMBR31DT, ZMBR42DT, ZMBR51DT, ZMBR61DT, ZMBR71DT, ZMBR81DT
      CL  Client (SPA)  (1):  ZMCL5ADTSR
      CR  Couples' Recode  (6):  ZMCR31DT, ZMCR42DT, ZMCR51DT, ZMCR61DT, ZMCR71DT, ZMCR81DT
      CT  Community Recode  (1):  ZMCT5ADTSR
      FC  Facility Inventory (SPA)  (2):  ZMFC5ADTSP, ZMFC5ADTSR
      GE  Geographic Data (GPS cluster coordinates)  (4):  ZMGE52FL, ZMGE61FL, ZMGE71FL, ZMGE81FL
      GR  Pregnancy and Postnatal Care Recode  (1):  ZMGR81DT
      HR  Household Recode  (7):  ZMHR21DT, ZMHR31DT, ZMHR42DT, ZMHR51DT, ZMHR61DT, ZMHR71DT, ZMHR81DT
      HT  Health Information System (SPA)  (1):  ZMHT41DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (3):  ZMHW21DT, ZMHW31DT, ZMHW42DT
      IP  Inpatient/Outpatient (SPA)  (1):  ZMIP5ADTSP
      IR  Individual Recode (Women)  (7):  ZMIR21DT, ZMIR31DT, ZMIR42DT, ZMIR51DT, ZMIR61DT, ZMIR71DT, ZMIR81DT
      KR  Children's Recode  (7):  ZMKR21DT, ZMKR31DT, ZMKR42DT, ZMKR51DT, ZMKR61DT, ZMKR71DT, ZMKR81DT
      LB  Labor & Delivery (SPA)  (2):  ZMLB5ADTSP, ZMLB5ADTSR
      MR  Men's Recode  (6):  ZMMR31DT, ZMMR41DT, ZMMR51DT, ZMMR61DT, ZMMR71DT, ZMMR81DT
      MS  Men's Raw  (2):  ZMMS5ADTSP, ZMMS5ADTSR
      NR  Pregnancies Recode  (1):  ZMNR81DT
      OI  Outpatient/Inpatient (SPA)  (1):  ZMOI5ADTSR
      OP  Outpatient (SPA)  (1):  ZMOP5ADTSP
      PH  Pharmacy (SPA)  (2):  ZMPH5ADTSP, ZMPH5ADTSR
      PM  PMTCT (SPA)  (1):  ZMPM5ADTSR
      PR  Household Member Recode  (7):  ZMPR21DT, ZMPR31DT, ZMPR43DT, ZMPR51DT, ZMPR61DT, ZMPR71DT, ZMPR81DT
      PV  Provider (SPA)  (2):  ZMPV5ADTSP, ZMPV5ADTSR
      SL  Staff / Provider Listing (SPA)  (1):  ZMSL5ADTSR
      SR  Siblings Recode  (1):  ZMSR81DT
      TB  TB Data (SPA)  (1):  ZMTB5ADTSR
      WI  Wealth Index  (2):  ZMWI31DT, ZMWI41DT

  [ZW] Zimbabwe  —  54 files across 13 recode types
      AR  HIV Test Results Recode  (3):  ZWAR51DT, ZWAR61DT, ZWAR71DT
      BR  Births Recode  (6):  ZWBR01DT, ZWBR31DT, ZWBR42DT, ZWBR52DT, ZWBR62DT, ZWBR72DT
      CR  Couples' Recode  (5):  ZWCR31DT, ZWCR41DT, ZWCR52DT, ZWCR62DT, ZWCR72DT
      GE  Geographic Data (GPS cluster coordinates)  (4):  ZWGE42FL, ZWGE52FL, ZWGE61FL, ZWGE72FL
      HH  Household Raw  (1):  ZWHH01DT
      HR  Household Recode  (5):  ZWHR31DT, ZWHR42DT, ZWHR52DT, ZWHR62DT, ZWHR72DT
      HW  Height and Weight Scores (WHO Child Growth Standards)  (4):  ZWHW01DT, ZWHW31DT, ZWHW41DT, ZWHW51DT
      IR  Individual Recode (Women)  (6):  ZWIR01DT, ZWIR31DT, ZWIR42DT, ZWIR52DT, ZWIR62DT, ZWIR72DT
      KR  Children's Recode  (6):  ZWKR01DT, ZWKR31DT, ZWKR42DT, ZWKR52DT, ZWKR62DT, ZWKR72DT
      MR  Men's Recode  (5):  ZWMR31DT, ZWMR41DT, ZWMR52DT, ZWMR62DT, ZWMR72DT
      PR  Household Member Recode  (5):  ZWPR31DT, ZWPR42DT, ZWPR52DT, ZWPR62DT, ZWPR72DT
      SQ  Service Provision recode (SPA)  (2):  ZWSQ02DT, ZWSQ30DT
      WI  Wealth Index  (2):  ZWWI31DT, ZWWI42DT
