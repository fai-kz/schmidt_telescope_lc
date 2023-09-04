<resource schema="schmidt_telescope_lc" resdir="schmidt_telescope_lc">
  <meta name="creationDate">2022-11-03T12:16:29Z</meta>

  <meta name="title">Archive of the FAI Schmidt telescope (large camera)</meta>

  <meta name="description">
The archive of digitized plates obtained on Schmidt telescope (large camera) at the Fesenkov Astrophysical Institute (FAI), Almaty, Kazakhstan. 
They represent the results of photometric observations of stars, comets, nebulae etc. for 50 years - from 1950 to 2000.    
  Observations were carried out in the optical range.
  </meta>
  <!-- Take keywords from 
    http://www.ivoa.net/rdf/uat
    if at all possible -->
  <meta name="subject">history-of-astronomy></meta>
  <meta name="subject">gaseous-nebulae</meta>
  <meta name="subject">comets</meta>
  <meta name="subject">field-of-view</meta>

  <meta name="creator">Fesenkov Astrophysical Institute</meta>
  <meta name="instrument">Schmidt telescope (large camera)</meta>
  <meta name="facility">Fesenkov Astrophysical Institute</meta>

  <!-- <meta name="source"></meta> -->
  <meta name="contentLevel">Research</meta>
  <meta name="type">Archive</meta>  <!-- or Archive, Survey, Simulation -->

  <meta name="coverage.waveband">Optical</meta>

  <table id="main" onDisk="True" mixin="//siap#pgs" adql="False">
    
    <mixin
      calibLevel="2"
      collectionName="'FAI Schmidt_lc'"
      targetName="objects[1]"
      expTime="EXPTIME"
    >//obscore#publishSIAP</mixin>
  
    <column name="object" type="char(15)[]"
      ucd="meta.id;src"
      tablehead="Objs."
      description="Name of object from the observation log."
      verbLevel="3"/>
    <column name="target_ra"
      unit="deg" ucd="pos.eq.ra;meta.main"
      tablehead="Target RA"
      description="Right ascension of object from observation log."
      verbLevel="1"/>
    <column name="target_dec"
      unit="deg" ucd="pos.eq.dec;meta.main"
      tablehead="Target Dec"
      description="Declination of object from observation log."
      verbLevel="1"/>
    <column name="exptime"
      unit="s" ucd="time.duration;obs.exposure"
      tablehead="T.Exp"
      description="Exposure time from observation log."
      verbLevel="5"/>
    <column name="observer" type="text"
      ucd="meta.id;obs.observer"
      tablehead="Obs. by."
      description="Observer name from observation log."
      verbLevel="20"/>
    <column name="telescope" type="text"
      ucd="instr.tel"
      tablehead="Telescope"
      description="Telescope from observation log."
      verbLevel="5"/>

  </table>

  <coverage>
    <updater sourceTable="main"/>
    <temporal>1950-01-01 2000-01-01</temporal>
  </coverage>

  <data id="import">
    <sources pattern="/var/gavo/inputs/astroplates/schmidt_telescope_lc/data/*.fit"/>

    <fitsProdGrammar>
      <rowfilter procDef="//products#define">
        <bind key="table">"\schema.main"</bind>
      </rowfilter>
    </fitsProdGrammar>

    <make table="main">
      <rowmaker>
        <simplemaps>
          exptime: EXPTIME,
          telescope: TELESCOP
        </simplemaps>
        <apply procDef="//siap#setMeta">
          <bind key="dateObs">@DATE_OBS</bind>

          <!-- bandpassId should be one of the keys from
            dachs adm dumpDF data/filters.txt;
            perhaps use //procs#dictMap for clean data from the header. -->
          <bind key="bandpassId">"Optical"</bind>

          <!-- pixflags is one of: C atlas image or cutout, F resampled, 
            X computed without interpolation, Z pixel flux calibrated, 
            V unspecified visualisation for presentation only 
          <bind key="pixflags"></bind> -->
          
          <!-- titles are what users usually see in a selection, so
            try to combine band, dateObs, object..., like
            "MyData {} {} {}".format(@DATE_OBS, @TARGET, @FILTER) -->
          <bind key="title">"{}_{}_{}_{}".format(@OBJECT, @DATEORIG, @EXPTIME, @PID)</bind>
        </apply>

        <apply procDef="//siap#getBandFromFilter"/>

        <apply procDef="//siap#computePGS"/>

        <map key="target_ra">hmsToDeg(@OBJCTRA, sepChar=":")</map>
        <map key="target_dec">dmsToDeg(@OBJCTDEC, sepChar=":")</map>
        <map key="observer" source="OBSERVER" nullExcs="KeyError"/>
        <map key="object">@mapped_names.split("|")</map>
      </rowmaker>
    </make>
  </data>

  <dbCore queriedTable="main" id="imagecore">
    <condDesc original="//siap#protoInput"/>
    <condDesc original="//siap#humanInput"/>
    <condDesc buildFrom="dateObs"/>
    <condDesc>
      <inputKey name="object" type="text" multiplicity="multiple"
          tablehead="Target Object" 
          description="Object being observed, Simbad-resolvable form"
          ucd="meta.name">
          <values fromdb="unnest(object) FROM schmidt_telescope_lc.main"/>
      </inputKey>
      <phraseMaker>
        <setup imports="numpy"/>
        <code><![CDATA[
          yield "%({})s && objects".format(
            base.getSQLKey("object", 
            numpy.array(inPars["object"]), outPars))
        ]]></code>
      </phraseMaker>
    </condDesc>
  </dbCore>

  <service id="web" allowed="form" core="imagecore">
    <meta name="shortName">schmidt_telescope_lc web</meta>
    <meta name="title">Web interface to FAI Schmidt telescope (large camera) archive</meta>
    <outputTable autoCols="accref,accsize,centerAlpha,centerDelta,
        dateObs,imageTitle">
      <outputField original="object">
        <formatter>
          return " - ".join(data)
        </formatter>
      </outputField>
    </outputTable>
  </service>

  <service id="i" allowed="form,siap.xml" core="imagecore">
    <meta name="shortName">schmidt_telescope_lc siap</meta>

    <meta name="sia.type">Pointed</meta>
    
    <meta name="testQuery.pos.ra">311.8</meta>
    <meta name="testQuery.pos.dec">30.4</meta>
    <meta name="testQuery.size.ra">0.1</meta>
    <meta name="testQuery.size.dec">0.1</meta>

    <!-- this is the VO publication -->
    <publish render="siap.xml" sets="ivo_managed"/>
    <!-- this puts the service on the root page -->
    <publish render="form" sets="local,ivo_managed" service="web"/>

  </service>

  <regSuite title="schmidt_telescope_lc regression">
    <!-- see http://docs.g-vo.org/DaCHS/ref.html#regression-testing
      for more info on these. -->

    <regTest title="schmidt_telescope_lc SIAP serves some data">
      <url POS="311.8,30.4" SIZE="0.1,0.1"
        >i/siap.xml</url>
      <code>
        rows = self.getVOTableRows()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["object"][0].strip(), "alf-Cyg")
        self.assertEqual(len(row["object"]), 1)
        self.assertEqual(row["imageTitle"], 
                'alf-Cyg_20-21.10.1985_20m_77S-77986.fit')
      </code>
    </regTest>

  </regSuite>
</resource>
