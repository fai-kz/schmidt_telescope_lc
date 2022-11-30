"""
This is a DaCHS processor (http://docs.g-vo.org/DaCHS/processors.html)
to add standard headers to FITS files from the FAI Schmidt telescope (large camera).
"""

import base64
import csv
import os
import re
import sys
import tempfile

import numpy

from gavo.helpers import fitstricks
from gavo import api

from gavo.helpers import anet


TELESCOPE_LATIN = {
  "50cm менисковый телескоп Максутова":
    "Wide aperture Maksutov meniscus telescope with main mirror 50 cm",
  "Большой Шмидт": "Schmidt large camera)",
  "Малый Шмидт": "Schmidt small camera)",
  None: "Provenance lost"}

    #foclen[mm],pltsize[cm],field[deg],coorplate_diam[mm],mirror_diam[mm] 
TELESCOPE_PARAM_DIC = { 
    "Wide aperture Maksutov meniscus telescope with main mirror 50 cm":
      [1200,[9,9.8],[5.2,5.7],500,660],
    "Schmidt telescope (large camera)": [773,[9,12],[6.2,9.9],397,None],
    "Schmidt telescope (small camera)": [170,[3.3,3.3],[10,10],None,190]}
    
OBSERVERS_LATIN = {
  'Рожковский Д.А.': 'Rozhkovskij D.A.', 
  'Торопова Т.П.':'Tropova T.P.', 
  'Городецкий Д.И.':'Gordetskij D.I.',
  'Глушков Ю.И.':'Glushkovskij Yu.I.',
  'Торопова Т.П.  Рожковский Д.А.': 'Tropova T.P., Rozhkovskij D.A.',
  'Рожковский Д.А., Торопова Т.П.' : 'Rozhkovskij D.A., Tropova T.P.', 
  'Рожковский Д.А., Павлова Л.А.' : 'Rozhkovskij D.A., Pavlova L.A.',
  'Карягина З.В.':'Karyagina Z.V.', 
  'Матягин В.С.': 'Matyagin V.S.', 
  'Павлова Л.А': 'Pavlova L.A.', 
  'Гаврилов': 'Gavrilov', 
  'Курчаков А.В.': 'Kurchakov A.V.',
  'Рожковский Д.А.   Городецкий Д.И.':'Rozhkovskij D.A.   Gordetskij D.I.',
  'Солодовников В.В.': 'Solodovnikov V.V.'}

METHOD_ENG = {"метод Меткофа": "Metkof method",
    "метод Меткофа-Блажко":"Metkof-Blazhko method"}


def parse_single_time(raw_time):
  """returns seconds of time for an h-m-s time string.

  Here is the syntax supported by the function.

  >>> parse_single_time("1h")
  3600.0
  >>> parse_single_time("4h30m")
  16200.0
  >>> parse_single_time("1h30m20s")
  5420.0
  >>> parse_single_time("20m")
  1200.0
  >>> parse_single_time("10.5m")
  630.0
  >>> parse_single_time("1m10s")
  70.0
  >>> parse_single_time("15s")
  15.0
  >>> parse_single_time("s23m")
  Traceback (most recent call last):
  ValueError: Cannot understand time 's23m'
  """
  mat = re.match(
    r"^(?P<hours>\d+(?:\.\d+)?h)?"
     r"(?P<minutes>\d+(?:\.\d+)?m)?"
    r"(?P<seconds>\d+(?:\.\d+)?s)?$", raw_time)
  if mat is None:
    raise ValueError(f"Cannot understand time '{raw_time}'")
  parts = mat.groupdict()

  return (float((parts["hours"] or "0h")[:-1])*3600
    + float((parts["minutes"] or "0m")[:-1])*60
    + float((parts["seconds"] or "0s")[:-1]))
  

def parse_exposure_times(raw_exp_times):
  """
  returns a list of floats giving the exposure times encoded in raw_exp_times.

  This is a ;-separated list of individual items.  see parse_single_time for
  details on the format.
  >>> parse_exposure_times("1h;2h;3h")
  [3600.0, 7200.0, 10800.0]
  >>> parse_exposure_times("1h30m20s;2h20m10s")
  [5420.0, 8410.0]
  >>> parse_exposure_times("1h30m20s;h20m10s")
  Traceback (most recent call last):
  ValueError: Cannot understand time 'h20m10s'
  """
  return [parse_single_time(raw_time) 
    for raw_time in raw_exp_times.split(";")]


def get_exposure_cards(raw_exp_times):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  exposure times.

  >>> get_exposure_cards("1h")
  {'EXPTIME': 3600.0}
  >>> get_exposure_cards("1h;5h")
  {'EXPTIME': 3600.0, 'EXPTIM1': 3600.0, 'EXPTIM2': 18000.0}
  """
  exptimes = parse_exposure_times(raw_exp_times)
  if len(exptimes)==1:
    return {"EXPTIME": exptimes[0]}
  else:
    retval = {"EXPTIME": exptimes[0]}
    retval.update(dict(
      (f"EXPTIM{n+1}", val) for n, val in enumerate(exptimes)))
    return retval


TIME_FORMATS = [re.compile(pat) for pat in [
  r"(?P<hours>\d+)h$",
  r"(?P<hours>\d+\.h\d+)$",
  r"(?P<hours>\d+)h(?P<minutes>\d+)m?$",
  r"(?P<hours>\d+h)(?P<minutes>\d+)m(?P<seconds>\d+)s?$",
]]
    
def reformat_single_time(raw_time):
  """  
  returns time in format hh:mm:ss

  >>> reformat_single_time("12.h5")
  '12:30:00'
  >>> reformat_single_time("2h23m23s")
  '02:23:23'
  >>> reformat_single_time("5h31")
  '05:31:00'
  >>> reformat_single_time("5h31m")
  '05:31:00'
  >>> reformat_single_time("13h54m24s")
  '13:54:24'
  >>> reformat_single_time("13h54m24")
  '13:54:24'
  >>> reformat_single_time("h20m2")
  Traceback (most recent call last):
  ValueError: Not a valid time h20m2
  """
  for pattern in TIME_FORMATS:
    mat = re.match(pattern, raw_time)
    if mat:
      break
  else:
    raise ValueError(f"Not a valid time {raw_time}")

  parts = mat.groupdict()
  hours = (float(parts.get("hours", 0).replace('h', ''))
    + float(parts.get("minutes", 0))/60.
    + float(parts.get("seconds", 0))/3600.)
  return api.hoursToHms(hours)


def reformat_time(raw_times):
  """
  returns time in format hh:mm:ss
  >>> reformat_time('2h23m23s;10h58m')
  ['02:23:23', '10:58:00']
  >>> reformat_time('5h31m;22h19m')
  ['05:31:00', '22:19:00']
  >>> reformat_time('1h54;13h49')
  ['01:54:00', '13:49:00']
  >>> reformat_time('2h23m23s;3h13m45s')
  ['02:23:23', '03:13:45']
  """
  return [reformat_single_time(time) for time in raw_times.split(";")]

def get_time_lt(raw_times):
  """
  returns local time of start/end of observations in format "LT hh:mm:ss"
  """
  return ['LT '+ time for time in reformat_time(raw_times)]

def get_time_lst(raw_times):
  """
  returns local sidereal time of start/end of observations in format "LST hh:mm:ss"
  """
  return ['LST '+ time for time in reformat_time(raw_times)]

def get_tms_cards_lst(raw_times):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local sidereal time of the start of observations.

  >>> get_tms_cards_lst("1h23m12s")
  {'TMS-ORIG': 'LST 01:23:12'}
  >>> get_tms_cards_lst("13h23m;5h13;12h15m54s")
  {'TMS-ORIG': 'LST 13:23:00', 'TMS-OR1': 'LST 13:23:00', 'TMS-OR2': 'LST 05:13:00', 'TMS-OR3': 'LST 12:15:54'}
  """
  times = get_time_lst(raw_times)
  if len(times)==1:
    return {"TMS-ORIG": times[0]}
  else:
    retval = {"TMS-ORIG": times[0]}
    retval.update(dict(
      (f"TMS-OR{n+1}", val) for n, val in enumerate(times)))
    return retval

def get_tms_cards_lt(raw_times):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local time of the start of observations.

  >>> get_tms_cards_lt("1h23m12s")
  {'TMS-ORIG': 'LT 01:23:12'}
  >>> get_tms_cards_lt("13h23m;5h13;12h15m54s")
  {'TMS-ORIG': 'LT 13:23:00', 'TMS-OR1': 'LT 13:23:00', 'TMS-OR2': 'LT 05:13:00', 'TMS-OR3': 'LT 12:15:54'}
  """
  times = get_time_lt(raw_times)
  if len(times)==1:
    return {"TMS-ORIG": times[0]}
  else:
    retval = {"TMS-ORIG": times[0]}
    retval.update(dict(
      (f"TMS-OR{n+1}", val) for n, val in enumerate(times)))
    return retval


def get_tme_cards_lst(raw_times):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local sidereal time of end of observations.

  >>> get_tme_cards_lst("1h23m12s")
  {'TME-ORIG': 'LST 01:23:12'}
  >>> get_tme_cards_lst("13h23m;5h13;12h15m54s")
  {'TME-ORIG': 'LST 13:23:00', 'TME-OR1': 'LST 13:23:00', 'TME-OR2': 'LST 05:13:00', 'TME-OR3': 'LST 12:15:54'}
  """
  times = get_time_lst(raw_times)
  if len(times)==1:
    return {"TME-ORIG": times[0]}
  else:
    retval = {"TME-ORIG": times[0]}
    retval.update(dict(
      (f"TME-OR{n+1}", val) for n, val in enumerate(times)))
    return retval

def get_tme_cards_lt(raw_times):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local (decret) time of the end of observations.

  >>> get_tme_cards_lt("1h23m12s")
  {'TME-ORIG': 'LT 01:23:12'}
  >>> get_tme_cards_lt("13h23m;5h13;12h15m54s")
  {'TME-ORIG': 'LT 13:23:00', 'TME-OR1': 'LT 13:23:00', 'TME-OR2': 'LT 05:13:00', 'TME-OR3': 'LT 12:15:54'}
  """
  times = get_time_lt(raw_times)
  if len(times)==1:
    return {"TME-ORIG": times[0]}
  else:
    retval = {"TME-ORIG": times[0]}
    retval.update(dict(
      (f"TME-OR{n+1}", val) for n, val in enumerate(times)))
    return retval

DEC_FORMATS = [re.compile(pat) for pat in [
  r"(?P<sign>-?)(?P<degrees>\d+\.?\d*)$",
  r"(?P<sign>-?)(?P<degrees>\d+) (?P<minutes>\d+)(?: (?P<seconds>\d+))?$",
]]

def dec_to_deg(raw_dec):
  """
  returns declanation as float in degrees.

  >>> dec_to_deg("29.06")
  29.06
  >>> dec_to_deg("-23.30")
  -23.3
  >>> "{:.5f}".format(dec_to_deg("50 41 45"))
  '50.69583'
  >>> "{:.5f}".format(dec_to_deg("-01 28 02"))
  '-1.46722'
  >>> "{:.5f}".format(dec_to_deg("-01 28"))
  '-1.46667'
  """
  for pattern in DEC_FORMATS:
    mat = re.match(pattern, raw_dec)
    if mat:
      break
  else:
    raise ValueError(f"Not a valid Dec {raw_dec}")

  parts = mat.groupdict()
  deg = (float(parts["degrees"])
    + float(parts.get("minutes", 0))/60.
    + float(parts.get("seconds", 0) or 0)/3600.)

  if parts["sign"]=="-":
    return -deg
  else:
    return deg


def reformat_dec(raw_dec):
  """
  returns declination in the format "dd:mm:ss".

  >>> reformat_dec("29.06")
  '+29:03:36'
  >>> reformat_dec("-23.30")
  '-23:18:00'
  >>> reformat_dec("50 41 45")
  '+50:41:45'
  >>> reformat_dec("-01 28 02")
  '-01:28:02'
  >>> reformat_dec("-01 28")
  '-01:28:00'
  """
  return api.degToDms(
    dec_to_deg(raw_dec), 
    sepChar=":", 
    secondFracs=0,
    preserveLeading=True)


RA_FORMATS = [re.compile(pat) for pat in [
  r"(?P<hours>\d+) (?P<minutes>\d+)(?: (?P<seconds>\d+))?$",
  r"(?P<hours>\d+)h(?P<minutes>\d+)m(?:(?P<seconds>\d+)s)?$",
  r"(?P<hours>\d+)h(?P<minutes>\d+)m?$",
]]


def ra_to_deg(raw_ra):
  """
  returns declanation as float in degrees.

  >>> "{:.5f}".format(ra_to_deg("05 32 49"))
  '83.20417'
  >>> ra_to_deg("05h33m")
  83.25
  >>> "{:.4f}".format(ra_to_deg("02h41m45s"))
  '40.4375'
  >>> ra_to_deg("01 28")
  22.0
  """  
  for pattern in RA_FORMATS:
    mat = re.match(pattern, raw_ra)
    if mat:
      break
  else:
    raise ValueError(f"Not a valid RA {raw_ra}")

  parts = mat.groupdict()
  hours = (float(parts["hours"])
    + float(parts["minutes"])/60.
    + float(parts["seconds"] or 0)/3600.)
  return hours/24*360


def reformat_ra(raw_ra):
  """
  returns right ascension in the format "hh:mm:ss"
  
  >>> reformat_ra("05 32 49")
  '05:32:49'
  >>> reformat_ra("05h33m")
  '05:33:00'
  >>> reformat_ra("02h41m45s")
  '02:41:45'
  >>> reformat_ra("01 28")
  '01:28:00'
  >>> reformat_ra("12h")
  Traceback (most recent call last):
  ValueError: Not a valid RA 12h
  """
  return api.degToHms(ra_to_deg(raw_ra), sepChar=":", secondFracs=0)


def expand_two_digit_year(raw_date):
  """inserts a 19 in front of the year part of a d.m.y raw_date if we
  sense a two-digit year.

  >>> expand_two_digit_year("30.x1.29")
  '30.x1.1929'
  >>> expand_two_digit_year("30.x1.1929")
  '30.x1.1929'
  """
  date_split = raw_date.split(".")
  if len(date_split[-1])==4:
    return raw_date  
  else:
    return f'{date_split[0]}.{date_split[1]}.19{date_split[2]}'


def parse_one_date(raw_date):
  """returns the first part of a date or date interval.
 
  >>> parse_one_date('13.03.1956')
  '13.03.1956'
  >>> parse_one_date('13.04.76')
  '13.04.1976'
  >>> parse_one_date('01-02.01.1964')
  '01.01.1964'
  >>> parse_one_date('01-02.01.64')
  '01.01.1964'
  >>> parse_one_date('31.08-01.09.1967')
  '31.08.1967'
  >>> parse_one_date('31.08-01.09.67')
  '31.08.1967'
  >>> parse_one_date('31.12.1965-01.01.1966')
  '31.12.1965'
  >>> parse_one_date('31.12.65-01.01.66')
  '31.12.1965'
  >>> parse_one_date('31.12.65-01.01.1966')
  '31.12.1965'
  >>> parse_one_date('31.12.1965-01.01.66')
  '31.12.1965'
  >>> parse_one_date('31.12.1965-01.66')
  Traceback (most recent call last):
  ValueError: not enough values to unpack (expected 3, got 2)
  """
  interval = raw_date.split("-")
  if len(interval)==1:
    start_parts = interval[0].split(".")

  else:
    # complete the start date from parts of the end date
    end_day, end_month, end_year = interval[1].split(".")
    start_parts = interval[0].rstrip(".").split(".")
    if len(start_parts)==1:
      start_parts.extend([end_month, end_year])
    elif len(start_parts)==2:
      start_parts.append(end_year)
  
  if len(start_parts[-1])==2:
    start_parts[-1] = "19"+start_parts[-1]

  return ".".join(start_parts)


def parse_date_list(raw_dates):
  """returns evening date of observations.

  For more information look at parse_one_date()

  >>> parse_date_list('13.03.1956;14.03.1956')
  ['13.03.1956', '14.03.1956']
  >>> parse_date_list('13.04.76;14.04.76')
  ['13.04.1976', '14.04.1976']
  >>> parse_date_list('01-02.01.1964;02-03.01.1964')
  ['01.01.1964', '02.01.1964']
  >>> parse_date_list('01-02.01.64;02-03.01.64')
  ['01.01.1964', '02.01.1964']
  >>> parse_date_list('31.08-01.09.1967;01-02.09.1967')
  ['31.08.1967', '01.09.1967']
  >>> parse_date_list('31.08-01.09.67;01-02.09.67')
  ['31.08.1967', '01.09.1967']
  >>> parse_date_list('31.12.1965-01.01.1966;01-02.01.1966')
  ['31.12.1965', '01.01.1966']
  >>> parse_date_list('31.12.65-01.01.66;01-02.01.66')
  ['31.12.1965', '01.01.1966']
  >>> parse_date_list('31.12.65-01.01.1966;01-02.01.1966')
  ['31.12.1965', '01.01.1966']
  >>> parse_date_list('31.12.1965-01.01.66;01-02.01.1966')
  ['31.12.1965', '01.01.1966']
  """
  return [parse_one_date(raw_date)
    for raw_date in raw_dates.split(";")]


def get_date_cards(raw_dates):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local sidereal time of the start of observations.

  >>> get_date_cards('13.03.1956')
  {'DATEORIG': '13.03.1956'}
  >>> get_date_cards('31.12.1965-01.01.66;01-02.01.1966')
  {'DATEORIG': '31.12.1965', 'DATEOR1': '31.12.1965', 'DATEOR2': '01.01.1966'}
  >>> get_date_cards('01-02.01.1964')
  {'DATEORIG': '01.01.1964'}
  """
  dates = parse_date_list(raw_dates)
  if len(dates)==1:
    return {"DATEORIG": dates[0]}
  else:
    retval = {"DATEORIG": dates[0]}
    retval.update(dict(
      (f"DATEOR{n+1}", val) for n, val in enumerate(dates)))
    return retval


def get_object_cards(raw_objects):
  """
  returns dictionary of keyword-value pairs for the FITS headers for our raw objects list

  >>> get_object_cards("Th4-4")
  {'OBJECT': 'Th4-4'}
  >>> get_object_cards("NGC6611;NGC6618")
  {'OBJECT': 'NGC6611', 'OBJECT1': 'NGC6611', 'OBJECT2': 'NGC6618'}
  """
  
  objects=raw_objects.split(";")
  if len(objects)==1:
    return {"OBJECT": objects[0]}
  else:
    retval = {"OBJECT": objects[0]}
    retval.update(dict(
      (f"OBJECT{n+1}",val) for n,val in enumerate(objects)))
    return retval


def run_tests(*args):
  """
  runs all doctests and exits the program.
  """
  import doctest
  sys.exit(doctest.testmod()[0])


def defuse_international_string(s):
  """returns a base64/utf-8-encoded version of a unicode string s.

  (as a string, not as bytes).

  >>> defuse_international_string("Максутова")
  '0JzQsNC60YHRg9GC0L7QstCw'
  """
  return base64.b64encode(s.encode("utf-8")).decode("ascii")


class PAHeaderAdder(api.AnetHeaderProcessor):
  indexPath = "/var/gavo/astrometry-indexes"
  sp_total_timelimit = 120
  sp_lower_pix = 2
  sp_upper_pix = 4
  sp_endob = 100
  sp_indices = ["index-2mass-1[012].fits"]

  sourceExtractorControl = """
    
    CATALOG_TYPE     FITS_1.0
    CATALOG_NAME     img.axy
    PARAMETERS_NAME  default.param
    FILTER           N
    DETECT_MINAREA   20
    DETECT_THRESH    6
    SEEING_FWHM      1.2
  """

  @staticmethod
  def addOptions(optParser):
    api.AnetHeaderProcessor.addOptions(optParser)
    optParser.add_option("--test", help="Run unit tests, then exit",
      action="callback", callback=run_tests)

  def _createAuxiliaries(self, dd):
    log_path = os.path.join(dd.rd.resdir, "logbook", "logbook.csv")
    with open(log_path, "r", encoding="utf-8") as f:
      rdr = csv.DictReader(f, delimiter=",")
      self.platemeta = dict((rec["ID"], rec) for rec in rdr)
  
  def NOobjectFilter(self, inName):
    """throws out funny-looking objects from inName as well as objects
    near the border.
    """
    hdulist = api.pyfits.open(inName)
    data = hdulist[1].data
    width = max(data.field("X_IMAGE"))
    height = max(data.field("Y_IMAGE"))
    badBorder = 0.2
    data = data[data.field("ELONGATION")<1.2]
    data = data[data.field("X_IMAGE")>width*badBorder]
    data = data[data.field("X_IMAGE")<width-width*badBorder]
    data = data[data.field("Y_IMAGE")>height*badBorder]
    data = data[data.field("Y_IMAGE")<height-height*badBorder]

    # the extra numpy.array below works around a bug in several versions
    # of pyfits that would write the full, not the filtered array
    hdu = api.pyfits.BinTableHDU(numpy.array(data))
    hdu.writeto("foo.xyls")
    hdulist.close()
    os.rename("foo.xyls", inName)

  def _shouldRunAnet(self, srcName, header):
    return True

  def _isProcessed(self, srcName):
    hdr = self.getPrimaryHeader(srcName)
    return "RA-ORIG" in hdr and "A_ORDER" in hdr

  def _mungeHeader(self, srcName, hdr):
    plateid = srcName.split(".")[-2].split("_")[-1]
    thismeta = self.platemeta[plateid]

#    mat = re.match(r"(\d\d)h(\d\d)m$", thismeta["RA"])
#    formatted_ra = "{}:{}".format(mat.group(1), mat.group(2))
#    mat = re.match(r"(\d\d)\.(\d\d)$", thismeta["DEC"])
#    formatted_dec = "{}:{}".format(mat.group(1), mat.group(2))

    #obj_type = thismeta["OBJTYPE"] #we will add the column with data later

    numexp=len(parse_exposure_times(thismeta["EXPTIME"]))
 
    telescope = TELESCOPE_LATIN[thismeta.get("TELESCOPE")]
    
    foclen = TELESCOPE_PARAM_DIC.get(telescope)[0]
    field = TELESCOPE_PARAM_DIC.get(telescope)[2]
    corr_plate_diameter = TELESCOPE_PARAM_DIC.get(telescope)[3]
    mirror_diameter =  TELESCOPE_PARAM_DIC.get(telescope)[4]
   
    if thismeta["SIZE"]:
        plate_size = thismeta["SIZE"].split("*")
    else:
        plate_size = TELESCOPE_PARAM_DIC.get(telescope)[1]

    observer = OBSERVERS_LATIN.get(thismeta["OBSERVER"])

    variable_arguments = get_exposure_cards(thismeta["EXPTIME"])
    variable_arguments.update(get_date_cards(thismeta["DATE-OBS"]))
    variable_arguments.update(get_object_cards(thismeta["OBJECT"]))
    if thismeta["TMS-LST"]:
      variable_arguments.update(get_tms_cards_lst(thismeta["TMS-LST"]))
    elif thismeta["TMS-LST"]:
      variable_arguments.update(get_tms_cards_lt(thismeta["TMS-LT"]))
    
    if thismeta["TME-LST"]:
      variable_arguments.update(get_tme_cards_lst(thismeta["TME-LST"]))
    else:
      variable_arguments.update(get_tme_cards_lt(thismeta["TME-LST"]))
   
    for to_delete in ["IRAF-MAX", "IRAF-MIN", "IRAF-BPX"]:
      del hdr[to_delete]

    return fitstricks.makeHeaderFromTemplate(
      fitstricks.WFPDB_TEMPLATE,
      originalHeader = hdr,
      RA_ORIG = reformat_ra(thismeta["RA"]),
      DEC_ORIG = reformat_dec(thismeta["DEC"]),
      RA_DEG = ra_to_deg(thismeta["RA"]),
      DEC_DEG = dec_to_deg(thismeta["DEC"]),
      OBSERVER = observer,
      OBSERVAT = "Fesenkov Astrophysical Institute",
      SITELONG = 43.17667,
      SITELAT = 76.96611,
      SITEELEV = 1450,
      TELESCOP = telescope,
      NUMEXP = numexp,
      SCANAUTH = "Shomshekova S., Umirbayeva A., Moshkina S.",
      ORIGIN = "Contant",
      FOCLEN = foclen,
      FOCUS = thismeta.get("FOCUS"),
      METHOD = METHOD_ENG.get(thismeta["METHOD"]),
      PLATESZ1 = plate_size[0],
      PLATESZ2 = plate_size[1],
      FIELD1 = field[0],
      FIELD2 = field[1],
      OTA_DIAM = mirror_diameter,
      OTA_APER = corr_plate_diameter,
      SCANERS1 = 1200,
      SCANERS2 = 1200,
      PRE_PROC = "Cleaning from dust with a squirrel brush and from contamination from the glass (not an emulsion) with paper napkins",
      PID = thismeta["ID"],
      FILTER = defuse_international_string(thismeta["FILTER"]),
      NOTES = defuse_international_string(thismeta["NOTES"]),
      PLATNOTE = defuse_international_string(thismeta["PLATNOTE"]),
      SCANNOTE = defuse_international_string(thismeta["SCANNOTE"]),
      OBSNOTE = defuse_international_string(thismeta["OBSNOTE"]),
      # Emulsion should really be translated
      EMULSION = defuse_international_string(thismeta["EMULSION"]),
      DETNAME = thismeta["DETNAME"],
      SKYCOND = thismeta["SKYCOND"],
      **variable_arguments)


if __name__=="__main__":
  api.procmain(PAHeaderAdder, "fai_schmidt_lc/q", "import")
