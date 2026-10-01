/**
 * ZamFarm Climate — Global Theme & Language Script
 * Load in <head> on every page.
 * Supports: English (en), Nyanja/Chewa (ny), Bemba (bem)
 */
(function () {
  'use strict';

  // ── 1. Dark mode — applied immediately to avoid flash ────────────────────
  try {
    if (localStorage.getItem('zf_dark') === 'true') {
      document.documentElement.setAttribute('data-theme', 'dark');
    }
  } catch (e) { /* localStorage blocked — ignore */ }

  // ── 2. Full translation dictionary ───────────────────────────────────────
  // Keys match every data-i18n attribute used in dashboard.html (and other pages).
  // Add a key to all three languages whenever a new string is tagged.
  var TRANSLATIONS = {

    // ── English (source / fallback) ───────────────────────────────────────
    en: {
      // Welcome / topbar
      welcomeBack:         'Welcome back',
      // Quick actions
      qaRunSim:            'Run Simulation',
      qaEarnPts:           'Earn +50 pts',
      qaYieldPred:         'Yield Prediction',
      qaAiForecast:        'AI forecast',
      qaCropAdvice:        'Crop Advice',
      qaBestCrop:          'Best crop for you',
      qaMyHistory:         'My History',
      qaAllPred:           'All predictions',
      qaMyOfficer:         'My Officer',
      qaGetAdvice:         'Get advice',
      qaMarketplace:       'Marketplace',
      qaBuySell:           'Buy & sell',
      qaFarmAssistant:     'Farm Assistant',
      qaAskAnything:       'Ask anything',
      // Stat chips
      hectares:            'Hectares',
      simulations:         'Simulations',
      totalPoints:         'Total Points',
      dayStreak:           'Day Streak',
      // Profile card / popup
      district:            'District',
      village:             'Village',
      phone:               'Phone',
      email:               'Email',
      farmSize:            'Farm Size',
      points:              'Points',
      sims:                'Sims',
      preds:               'Preds',
      editProfile:         'Edit Profile',
      progressWord:        'Progress',
      logout:              'Logout',
      // Profile edit modal
      changePhoto:         'Change Photo',
      fullName:            'Full Name',
      cancel:              'Cancel',
      saveChanges:         'Save Changes',
      // Farm info card
      farmInformation:     'Farm Information',
      // Weather widget
      liveWeather:         'Live Weather',
      rain:                'Rain',
      humid:               'Humid',
      wind:                'Wind',
      // Quick simulator widget
      quickSimulator:      'Quick Simulator',
      normal:              'Normal',
      drought:             'Drought',
      above:               'Above',
      maize:               'Maize',
      soya:                'Soya',
      gnuts:               'Gnuts',
      cassava:             'Cassava',
      runAndEarn:          'Run & Earn +50',
      // Chart titles
      yieldTrend:          'Yield Trend',
      cropMix:             'Crop Mix',
      yieldBySoil:         'Yield by Soil Type',
      yieldEfficiency:     'Yield Efficiency (T/ha)',
      financialPerformance:'Financial Performance by Crop',
      // Chart subtitles
      avgYieldPerSoil:     'Average yield (T/ha) per soil type across all your predictions',
      yieldPerHaOverTime:  'Your yield per hectare over time — higher = more efficient farming',
      financialDesc:       'Estimated gross revenue vs total cost vs net profit per crop (ZMW)',
      // Empty states
      noPredictionsYet:    'No predictions yet —',
      makeFirstOne:        'make your first →',
      noDataYet:           'No data yet.',
      makePredictionsSoil: 'Make predictions on different soil types to see comparison.',
      noEfficiencyYet:     'No efficiency data yet.',
      noFinancialYet:      'No financial data yet. Make predictions to see analysis.',
      // Predictions table
      recentPredictions:   'Recent Predictions',
      viewAll:             'View All',
      crop:                'Crop',
      yield:               'Yield',
      date:                'Date',
      loading:             'Loading…',
      // Officer panel
      yourExtensionOfficer:'Your Extension Officer',
      loadingOfficer:      'Loading your officer…',
      // Notifications panel
      notificationsMessages:'Notifications & Messages',
      loadingNotifs:       'Loading notifications…',
      // Settings panel
      settings:            'Settings',
      appearance:          'Appearance',
      darkMode:            'Dark Mode',
      darkModeSub:         'Switch to a darker interface',
      compactSidebar:      'Compact Sidebar',
      compactSub:          'Show only icons',
      language:            'Language',
      interfaceLang:       'Interface Language',
      langSub:             'English, Nyanja & Bemba',
      notificationsWord:   'Notifications',
      officerMessages:     'Officer Messages',
      officerMsgSub:       'Show messages from your officer',
      pointsAlerts:        'Points Alerts',
      pointsAlertsSub:     'Notify when you earn points',
      weatherAlerts:       'Weather Alerts',
      weatherAlertsSub:    'District weather updates',
      account:             'Account',
      editProfileSub:      'Photo, name, phone, location, farm size',
      editBtn:             'Edit',
      nameWord:            'Name',
      logoutSub:           'Sign out of your account',
      // Login reward
      dailyLoginPts:       'Daily login points earned!',
      comeBackTomorrow:    'Come back tomorrow for more 🌿',
      // Sidebar
      smartAgriculture:    'Smart Agriculture',
      mainMenu:            'Main Menu',
      dashboard:           'Dashboard',
      yieldPrediction:     'Yield Prediction',
      predictionHistory:   'Prediction History',
      cropRecommendation:  'Crop Recommendation',
      gamification:        'Gamification',
      investmentSimulator: 'Investment Simulator',
      myProgress:          'My Progress',
      leaderboard:         'Leaderboard',
      climateTools:        'Climate Tools',
      dataIngestion:       'Data Ingestion',
      seasonForecast:      'Season Forecast',
      discover:            'Discover',
      marketplace:         'Marketplace',
      farmAssistant:       'Farm Assistant',
      helpSupport:         'Help & Support',
      aboutSystem:         'About System',
      // Predict Yield page
      aiYieldPrediction:    'AI Yield Prediction',
      predictIntro:         'Enter your farm details to get an AI-powered yield forecast using live climate data from',
      predictionParameters: 'Prediction Parameters',
      selectCrop:           'Select Crop',
      liveClimateUsed:      'Live Climate Used',
      temperature:          'Temperature',
      rainfall:             'Rainfall',
      loadingDistrictWeather: 'Loading district weather…',
      aiModelPrediction:    'AI Model Prediction',
      agronomicEstimate:    'Agronomic Estimate',
      predictionResult:     'Prediction Result',
      predictedYield:       'Predicted Yield',
      metricTonsTotal:      'Metric Tons Total',
      yieldVsBenchmark:     'Your yield vs Zambia benchmark',
      awaitingPrediction:   'Awaiting Prediction',
      awaitingPredictionDesc: 'Select a crop, enter your hectares, and click <strong>Predict Yield</strong> to see your AI-powered forecast.',
      couldNotLoadHistory:  'Could not load history.',
      ready:                'Ready',
      // Simulator page
      cropInvestmentSimulator: 'Crop Investment Simulator',
      navigation:           'Navigation',
      simulator:             'Simulator',
      readyToSimulate:       'Ready to Simulate',
      readyToSimulateDesc:   'Select a crop and scenario on the left, then click <strong>Run Simulation</strong> to see yield forecast, risk level &amp; investment return.',
      earn50Points:          'Earn 50 Points',
      unlockBadges:          'Unlock Badges',
      suitability:           'Suitability',
      cropSuitability:       'Crop Suitability',
      totalYield:            'Total Yield',
      seasonalEstimate:      'Seasonal estimate',
      netProfit:             'Net Profit',
      inputCost:             'Input Cost',
      revenue:               'Revenue',
      recentSimulations:     'Recent Simulations',
      recentSimulationsDesc: 'Your last {n} simulations. Compare crops and scenarios at a glance.',
      scenario:              'Scenario',
      yieldTHa:              'Yield (T/ha)',
      netProfitZmw:          'Net Profit (ZMW)',
      risk:                  'Risk',
    },

    // ── Nyanja / Chewa ────────────────────────────────────────────────────
    ny: {
      // Welcome / topbar
      welcomeBack:         'Takulandirani',
      // Quick actions
      qaRunSim:            'Yendetsani Kuwombeza',
      qaEarnPts:           'Pezani +50 maguwa',
      qaYieldPred:         'Kunenezera Zokolola',
      qaAiForecast:        'Chinenero cha AI',
      qaCropAdvice:        'Malangizo a Mbeu',
      qaBestCrop:          'Mbeu yabwino kwa inu',
      qaMyHistory:         'Mbiri Yanga',
      qaAllPred:           'Zonenezedwa zonse',
      qaMyOfficer:         'Ofisa Wanga',
      qaGetAdvice:         'Pezani malangizo',
      qaMarketplace:       'Msika',
      qaBuySell:           'Gula ndi kugulitsa',
      qaFarmAssistant:     'Woтhandizа Mlimi',
      qaAskAnything:       'Funsani chilichonse',
      // Stat chips
      hectares:            'Maekala',
      simulations:         'Kuwombeza',
      totalPoints:         'Maguwa Onse',
      dayStreak:           'Masiku Otsatizana',
      // Profile card / popup
      district:            'Dipatimenti',
      village:             'Mudzi',
      phone:               'Foni',
      email:               'Imelo',
      farmSize:            'Kukula kwa Munda',
      points:              'Maguwa',
      sims:                'Kuwombeza',
      preds:               'Zonenezedwa',
      editProfile:         'Sinthani Mbiri Yanu',
      progressWord:        'Mapeto',
      logout:              'Tuluka',
      // Profile edit modal
      changePhoto:         'Sinthani Chithunzi',
      fullName:            'Dzina Lonse',
      cancel:              'Siyani',
      saveChanges:         'Sungani Zosintha',
      // Farm info card
      farmInformation:     'Chidziwitso cha Munda',
      // Weather widget
      liveWeather:         'Nyengo Yamakono',
      rain:                'Mvula',
      humid:               'Chinyontho',
      wind:                'Mphepo',
      // Quick simulator widget
      quickSimulator:      'Kuwombeza Msanga',
      normal:              'Wamba',
      drought:             'Chilala',
      above:               'Kupitirira',
      maize:               'Chimanga',
      soya:                'Soya',
      gnuts:               'Nzama',
      cassava:             'Chinangwa',
      runAndEarn:          'Yendetsa &amp; Peza +50',
      // Chart titles
      yieldTrend:          'Kuyenda kwa Zokolola',
      cropMix:             'Mitundu ya Mbeu',
      yieldBySoil:         'Zokolola pa Mtundu wa Nthaka',
      yieldEfficiency:     'Kugwira Ntchito kwa Munda (T/ha)',
      financialPerformance:'Ndalama za Mbeu Iliyonse',
      // Chart subtitles
      avgYieldPerSoil:     'Zokolola zapakati (T/ha) pa mtundu wa nthaka mwa zonenezedwa zanu',
      yieldPerHaOverTime:  'Zokolola pa hekitala pakapita nthawi — zazikulu = ntchito yadzi',
      financialDesc:       'Ndalama zapachidule vs ndalama zamtengo vs phindu la mbeu (ZMW)',
      // Empty states
      noPredictionsYet:    'Palibe zonenezedwa — ',
      makeFirstOne:        'yambani →',
      noDataYet:           'Palibe deta.',
      makePredictionsSoil: 'Nenezani pa mitundu yosiyanasiyana ya nthaka kuti muone.',
      noEfficiencyYet:     'Palibe deta ya kugwira ntchito.',
      noFinancialYet:      'Palibe deta ya ndalama. Nenezani kuti muone.',
      // Predictions table
      recentPredictions:   'Zonenezedwa Zamakono',
      viewAll:             'Onani Zonse',
      crop:                'Mbeu',
      yield:               'Zokolola',
      date:                'Tsiku',
      loading:             'Kutsikira…',
      // Officer panel
      yourExtensionOfficer:'Ofisa Wanu wa Kulima',
      loadingOfficer:      'Kutsikira ofisa wanu…',
      // Notifications panel
      notificationsMessages:'Zodziwitsa ndi Mauthenga',
      loadingNotifs:       'Kutsikira zodziwitsa…',
      // Settings panel
      settings:            'Zokhazikika',
      appearance:          'Maonekedwe',
      darkMode:            'Njira Yodima',
      darkModeSub:         'Sinthani kwa chithunzi chofewa',
      compactSidebar:      'Mbali Yofupikitsidwa',
      compactSub:          'Onetsa zilankhulo zokha',
      language:            'Chilankhulo',
      interfaceLang:       'Chilankhulo cha Machitidwe',
      langSub:             'Chingerezi, Chinyanja & Chibemba',
      notificationsWord:   'Zodziwitsa',
      officerMessages:     'Mauthenga a Ofisa',
      officerMsgSub:       'Onetsa mauthenga kuchoka kwa ofisa wanu',
      pointsAlerts:        'Zodziwitsa za Maguwa',
      pointsAlertsSub:     'Dziwitsa mukalandira maguwa',
      weatherAlerts:       'Zodziwitsa za Nyengo',
      weatherAlertsSub:    'Zosintha za nyengo pa dipatimenti lanu',
      account:             'Akaunti',
      editProfileSub:      'Chithunzi, dzina, foni, malo, kukula kwa munda',
      editBtn:             'Sinthani',
      nameWord:            'Dzina',
      logoutSub:           'Tulukani mu akaunti yanu',
      // Login reward
      dailyLoginPts:       'Maguwa a lolowera lowelo apezeka!',
      comeBackTomorrow:    'Bwererani mawa kuti mupeze zambiri 🌿',
      // Sidebar
      smartAgriculture:    'Ulimi Wanzeru',
      mainMenu:            'Menyu Yayikulu',
      dashboard:           'Bwalo Lalikulu',
      yieldPrediction:     'Kunenezera Zokolola',
      predictionHistory:   'Mbiri ya Zonenezedwa',
      cropRecommendation:  'Malangizo a Mbeu',
      gamification:        'Masewera a Maguwa',
      investmentSimulator: 'Kuwombeza Ndalama',
      myProgress:          'Mapeto Anga',
      leaderboard:         'Mzere wa Anthu',
      climateTools:        'Zida za Nyengo',
      dataIngestion:       'Kulowetsa Deta',
      seasonForecast:      'Kanema ka Nyengo',
      discover:            'Kufunafuna',
      marketplace:         'Msika',
      farmAssistant:       'Wothandiza Mlimi',
      helpSupport:         'Thandizo',
      aboutSystem:         'Za Dongosolo',
      // Predict Yield page
      aiYieldPrediction:    'Kulosera Zokolola ndi AI',
      predictIntro:         'Lowetsani zambiri za munda wanu kuti mupeze kulosera kwa zokolola pogwiritsa ntchito deta ya nyengo yochokera ku',
      predictionParameters: 'Zofunika pa Kulosera',
      selectCrop:           'Sankhani Mbewu',
      liveClimateUsed:      'Nyengo Yogwiritsidwa Ntchito',
      temperature:          'Kutentha',
      rainfall:             'Mvula',
      loadingDistrictWeather: 'Kutsitsa nyengo ya dera…',
      aiModelPrediction:    'Kulosera kwa AI',
      agronomicEstimate:    'Kuyerekezera kwa Ulimi',
      predictionResult:     'Zotsatira za Kulosera',
      predictedYield:       'Zokolola Zoyembekezeredwa',
      metricTonsTotal:      'Matani Onse',
      yieldVsBenchmark:     'Zokolola zanu poyerekeza ndi muyezo wa Zambia',
      awaitingPrediction:   'Kuyembekezera Kulosera',
      awaitingPredictionDesc: 'Sankhani mbewu, lowetsani hekitala zanu, ndikudina <strong>Predict Yield</strong> kuti muwone kulosera kwa AI.',
      couldNotLoadHistory:  'Sitinathe kutsitsa mbiri.',
      ready:                'Wakonzeka',
      // Simulator page
      cropInvestmentSimulator: 'Chiwerengero cha Ndalama mu Mbewu',
      navigation:           'Kuyendetsa',
      simulator:             'Chowerengera',
      readyToSimulate:       'Wokonzeka Kuyesa',
      readyToSimulateDesc:   'Sankhani mbewu ndi mkhalidwe wa nyengo kumanzere, kenako dinani <strong>Run Simulation</strong> kuti muwone zokolola, chiopsezo ndi phindu.',
      earn50Points:          'Peza Mfundo 50',
      unlockBadges:          'Tsekulani Zibadge',
      suitability:           'Kuyenerera',
      cropSuitability:       'Kuyenerera kwa Mbewu',
      totalYield:            'Zokolola Zonse',
      seasonalEstimate:      'Kuyerekezera kwa Nyengo',
      netProfit:             'Phindu Lenileni',
      inputCost:             'Mtengo wa Zogwiritsa Ntchito',
      revenue:               'Ndalama Zolowa',
      recentSimulations:     'Kuyesa Kwaposachedwa',
      recentSimulationsDesc: 'Kuyesa kwanu {n} kwaposachedwa. Yerekezerani mbewu ndi mikhalidwe ya nyengo.',
      scenario:              'Mkhalidwe',
      yieldTHa:              'Zokolola (T/ha)',
      netProfitZmw:          'Phindu Lenileni (ZMW)',
      risk:                  'Chiopsezo',
    },

    // ── Bemba ─────────────────────────────────────────────────────────────
    bem: {
      // Welcome / topbar
      welcomeBack:         'Mwaishibukwa',
      // Quick actions
      qaRunSim:            'Shingilileni Ukubomba',
      qaEarnPts:           'Mununshine +50 amaponto',
      qaYieldPred:         'Ukubula Insalilo',
      qaAiForecast:        'Ukubula kwa AI',
      qaCropAdvice:        'Amatontonkanya ya Fibuto',
      qaBestCrop:          'Ichibuto ichibomba kuli imwe',
      qaMyHistory:         'Amakani Yandi',
      qaAllPred:           'Ukukubula konse',
      qaMyOfficer:         'Mulumbi Wandi',
      qaGetAdvice:         'Pobeni amatontonkanya',
      qaMarketplace:       'Isoko',
      qaBuySell:           'Sumpeni ne kugulisha',
      qaFarmAssistant:     'Umwishibilo wa Ulimi',
      qaAskAnything:       'Ipusha chilichonse',
      // Stat chips
      hectares:            'Mahekitala',
      simulations:         'Ukubomba',
      totalPoints:         'Amaponto Yonse',
      dayStreak:           'Insiku Ishindilishiwa',
      // Profile card / popup
      district:            'Ichipinda',
      village:             'Umushi',
      phone:               'Ifoni',
      email:               'Imelo',
      farmSize:            'Ubukulu bwa Mpanga',
      points:              'Amaponto',
      sims:                'Ukubomba',
      preds:               'Ukukubula',
      editProfile:         'Lunduleni Amakani Yenu',
      progressWord:        'Ifyafikiwa',
      logout:              'Fuma',
      // Profile edit modal
      changePhoto:         'Sunga Ifipikisha',
      fullName:            'Ishina Lyonse',
      cancel:              'Siyeni',
      saveChanges:         'Sungeni Ifyasunga',
      // Farm info card
      farmInformation:     'Amakani ya Mpanga',
      // Weather widget
      liveWeather:         'Imvula ya Nomba',
      rain:                'Imvula',
      humid:               'Ubushishi',
      wind:                'Umwela',
      // Quick simulator widget
      quickSimulator:      'Ukubomba Ukucimbilila',
      normal:              'Fye',
      drought:             'Insala ya Mvula',
      above:               'Kupita',
      maize:               'Amasaka',
      soya:                'Isoya',
      gnuts:               'Impande',
      cassava:             'Ubwali',
      runAndEarn:          'Shingilileni &amp; Pobeni +50',
      // Chart titles
      yieldTrend:          'Ukuya kwa Insalilo',
      cropMix:             'Ifyabuto Ifishingi',
      yieldBySoil:         'Insalilo pa Ubuta bwa Iftonde',
      yieldEfficiency:     'Ukubomba kwa Mpanga (T/ha)',
      financialPerformance:'Ndalama sha Ichibuto',
      // Chart subtitles
      avgYieldPerSoil:     'Insalilo ya pakati (T/ha) pa ubuta bwa iftonde mu ukukubula kwenu',
      yieldPerHaOverTime:  'Insalilo pa hekitala mu nthawi — yacine = ukubomba kwabwino',
      financialDesc:       'Ndalama sha pachidule vs sha amenso vs phindu lya ichibuto (ZMW)',
      // Empty states
      noPredictionsYet:    'Tapali ukukubula — ',
      makeFirstOne:        'ambilisheni →',
      noDataYet:           'Tapali amakani.',
      makePredictionsSoil: 'Bubulisheni pa ifyabuta fyonse ukubona.',
      noEfficiencyYet:     'Tapali amakani ya ukubomba.',
      noFinancialYet:      'Tapali amakani ya ndalama. Bubulisheni ukubona.',
      // Predictions table
      recentPredictions:   'Ukukubula kwa Nomba',
      viewAll:             'Moneni Fyonse',
      crop:                'Ichibuto',
      yield:               'Insalilo',
      date:                'Lusiku',
      loading:             'Kulondolola…',
      // Officer panel
      yourExtensionOfficer:'Mulumbi Wenu wa Ulimi',
      loadingOfficer:      'Kulondolola mulumbi wenu…',
      // Notifications panel
      notificationsMessages:'Amakani ne Buumba',
      loadingNotifs:       'Kulondolola amakani…',
      // Settings panel
      settings:            'Ilyashi lya Bubombi',
      appearance:          'Ukuboneka',
      darkMode:            'Umuswamo Wakudima',
      darkModeSub:         'Sunga ku muswamo ukudima',
      compactSidebar:      'Ulusengo Olufupikishiwa',
      compactSub:          'Bonesheni fyebo fye',
      language:            'Ulimi',
      interfaceLang:       'Ulimi wa Ukubomba',
      langSub:             'Ciingelesa, Cinyanja & Icibemba',
      notificationsWord:   'Amakani',
      officerMessages:     'Ubuumba bwa Mulumbi',
      officerMsgSub:       'Bonesheni ubuumba uboola kuli mulumbi wenu',
      pointsAlerts:        'Amakani ya Amaponto',
      pointsAlertsSub:     'Makisheni nomba mununshisha amaponto',
      weatherAlerts:       'Amakani ya Imvula',
      weatherAlertsSub:    'Ilyashi lya imvula mu ichipinda cenu',
      account:             'Akaonti',
      editProfileSub:      'Ifipikisha, ishina, ifoni, inshila, ubukulu bwa mpanga',
      editBtn:             'Lunduleni',
      nameWord:            'Ishina',
      logoutSub:           'Fumeni mu akaonti yenu',
      // Login reward
      dailyLoginPts:       'Amaponto ya kulowela lyuba yapobiwa!',
      comeBackTomorrow:    'Bweleni mabilo ukupoba afyine 🌿',
      // Sidebar
      smartAgriculture:    'Ulimi Ufumya Amaano',
      mainMenu:            'Menu Iipela',
      dashboard:           'Ichikala',
      yieldPrediction:     'Ukubula Insalilo',
      predictionHistory:   'Amakani ya Insalilo',
      cropRecommendation:  'Amatontonkanya ya Fibuto',
      gamification:        'Masewela ya Amaponto',
      investmentSimulator: 'Ukubula Ndalama',
      myProgress:          'Ifyafikiwa Fyandi',
      leaderboard:         'Umuzikile',
      climateTools:        'Ifya Imvula',
      dataIngestion:       'Ukufungulila Amakani',
      seasonForecast:      'Ukulolela Mpundu',
      discover:            'Ukusansala',
      marketplace:         'Isoko',
      farmAssistant:       'Umwishibilo wa Mpanga',
      helpSupport:         'Icisambililo',
      aboutSystem:         'Pali Dongosolo',
      // Predict Yield page
      aiYieldPrediction:    'Ukubula Insalilo na AI',
      predictIntro:         'Bikeni amakani ya mpanga wenu pa kuti mupeleko ukubula kwa insalilo ukubomfya amakani ya imvula ukufuma ku',
      predictionParameters: 'Amakani ya Ukubula',
      selectCrop:           'Saluleni Icibuto',
      liveClimateUsed:      'Imvula Iyabomfiwa',
      temperature:          'Ubushika',
      rainfall:             'Imvula',
      loadingDistrictWeather: 'Ukufungulila imvula ya chipinda…',
      aiModelPrediction:    'Ukubula kwa AI',
      agronomicEstimate:    'Ukupendelela kwa Ulimi',
      predictionResult:     'Ifyafuma mu Kubula',
      predictedYield:       'Insalilo Yalolelwa',
      metricTonsTotal:      'Amatani Yense',
      yieldVsBenchmark:     'Insalilo yenu na muyeo wa Zambia',
      awaitingPrediction:   'Ulekutali Ukubula',
      awaitingPredictionDesc: 'Saluleni icibuto, bikeni amahekita yenu, mulyo mucindike <strong>Predict Yield</strong> pakuti mumone ukubula kwa AI.',
      couldNotLoadHistory:  'Tatwakwete ukufungulila amakani.',
      ready:                'Naliupa',
      // Simulator page
      cropInvestmentSimulator: 'Ukubika Indalama mu Cibuto',
      navigation:           'Ukutungulula',
      simulator:             'Icipimo',
      readyToSimulate:       'Naliupa Ukupima',
      readyToSimulateDesc:   'Saluleni icibuto ne mpindi ya mvula ku kuso, mulyo mucindike <strong>Run Simulation</strong> pakuti mumone insalilo, ubusanso, ne fyabwesha indalama.',
      earn50Points:          'Ikatako Amapoints 50',
      unlockBadges:          'Vuula Utubadge',
      suitability:           'Ukuwama',
      cropSuitability:       'Ukuwama kwa Icibuto',
      totalYield:            'Insalilo Yonse',
      seasonalEstimate:      'Ukupendelela kwa Mpindi',
      netProfit:             'Indalama Shafuma',
      inputCost:             'Indalama Shabomfiwa',
      revenue:               'Indalama Shaingila',
      recentSimulations:     'Ifipimo Fyapapena',
      recentSimulationsDesc: 'Ifipimo fyenu {n} ifyapapena. Pashanyeni ifibuto ne mpindi ya mvula.',
      scenario:              'Imipindi',
      yieldTHa:              'Insalilo (T/ha)',
      netProfitZmw:          'Indalama Shafuma (ZMW)',
      risk:                  'Ubusanso',
    },
  };

  // ── 3. Apply language to the page ────────────────────────────────────────
  function applyLanguage() {
    try {
      var lang   = localStorage.getItem('zf_lang') || 'en';
      var labels = TRANSLATIONS[lang] || TRANSLATIONS['en'];
      var en     = TRANSLATIONS['en'];

      // (A) Translate elements tagged with data-i18n (new system)
      document.querySelectorAll('[data-i18n]').forEach(function (el) {
        var key = el.getAttribute('data-i18n');
        var val = labels[key];
        if (val === undefined) val = en[key];   // English fallback
        if (val === undefined) return;

        // Support a {n} token for elements carrying a data-count attribute
        // (e.g. "Your last {n} simulations.") so pluralised numbers survive translation.
        var countAttr = el.getAttribute('data-count');
        if (countAttr !== null && val.indexOf('{n}') !== -1) {
          val = val.replace('{n}', countAttr);
        }

        // Strings that legitimately contain inline HTML (e.g. <strong>) are
        // marked with data-i18n-html so we use innerHTML; everything else
        // uses textContent to avoid any injection risk from translated text.
        if (el.hasAttribute('data-i18n-html')) {
          el.innerHTML = val;
        } else {
          el.textContent = val;
        }
      });

      // (B) Backward-compat: old data-lang-key attribute
      document.querySelectorAll('[data-lang-key]').forEach(function (el) {
        var key = el.getAttribute('data-lang-key');
        var val = labels[key] || (en[key]);
        if (val !== undefined) el.textContent = val;
      });

      // (C) Update the langSelect dropdown to reflect current language
      var ls = document.getElementById('langSelect');
      if (ls) ls.value = lang;

      // (D) Store lang code on <html> for CSS targeting
      document.documentElement.setAttribute('lang', lang.split('-')[0]);
    } catch (e) { /* silent — never break the page */ }
  }

  // ── 4. Apply compact sidebar ─────────────────────────────────────────────
  function applyCompact() {
    try {
      if (localStorage.getItem('zf_compact') !== 'true') return;
      var sb = document.getElementById('sidebar');
      var tb = document.getElementById('topbar');
      var mc = document.getElementById('mainContent');
      if (sb) sb.classList.add('collapsed');
      if (window.innerWidth > 900) {
        if (tb) tb.style.left       = '68px';
        if (mc) mc.style.marginLeft = '68px';
      }
      var ct = document.getElementById('compactToggle');
      if (ct) ct.checked = true;
    } catch (e) { /* silent */ }
  }

  // ── 5. Dark mode sync ────────────────────────────────────────────────────
  function syncDarkToggle() {
    try {
      var tog = document.getElementById('darkModeToggle');
      if (tog) tog.checked = localStorage.getItem('zf_dark') === 'true';
    } catch (e) { /* silent */ }
  }

  // ── 6. Wire event listeners ──────────────────────────────────────────────
  function attachListeners() {
    // Dark mode toggle
    var darkTog = document.getElementById('darkModeToggle');
    if (darkTog) {
      darkTog.addEventListener('change', function () {
        var on = this.checked;
        document.documentElement.setAttribute('data-theme', on ? 'dark' : 'light');
        try { localStorage.setItem('zf_dark', String(on)); } catch (e) { /* silent */ }
      });
    }

    // Language selector — re-apply immediately on every change
    var langSel = document.getElementById('langSelect');
    if (langSel) {
      langSel.addEventListener('change', function () {
        try { localStorage.setItem('zf_lang', this.value); } catch (e) { /* silent */ }
        applyLanguage();
      });
    }
  }

  // ── 7. Run after DOM is ready ────────────────────────────────────────────
  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    applyCompact();
    applyLanguage();
    syncDarkToggle();
    attachListeners();
  });

  // ── 8. Expose public API ─────────────────────────────────────────────────
  window.ZF = window.ZF || {};
  window.ZF.applyDark = function (on) {
    document.documentElement.setAttribute('data-theme', on ? 'dark' : 'light');
    try { localStorage.setItem('zf_dark', String(on)); } catch (e) { /* silent */ }
    var tog = document.getElementById('darkModeToggle');
    if (tog) tog.checked = on;
  };
  window.ZF.applyLanguage = applyLanguage;
  window.ZF.applyCompact  = applyCompact;
  window.ZF.getLang = function () {
    try { return localStorage.getItem('zf_lang') || 'en'; } catch (e) { return 'en'; }
  };
  window.ZF.getTranslation = function (key) {
    var lang   = window.ZF.getLang();
    var labels = TRANSLATIONS[lang] || TRANSLATIONS['en'];
    return labels[key] || (TRANSLATIONS['en'][key]) || key;
  };
  window.ZF.t = window.ZF.getTranslation; // short alias for page-level JS

  // ── 9. Copyright footer ──────────────────────────────────────────────────
  (function () {
    function addFooter() {
      if (document.getElementById('zfCopyright')) return;
      var footer = document.createElement('div');
      footer.id = 'zfCopyright';
      footer.innerHTML = '&copy; ' + new Date().getFullYear() +
        ' ZamFarm Climate Connect. All Rights Reserved.';
      footer.style.cssText = [
        'text-align:center',
        'font-family:Outfit,sans-serif',
        'font-size:.72rem',
        'font-weight:600',
        'color:#999',
        'padding:14px 10px 20px',
        'opacity:.85'
      ].join(';');
      document.body.appendChild(footer);
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', addFooter);
    } else {
      addFooter();
    }
  })();

})();