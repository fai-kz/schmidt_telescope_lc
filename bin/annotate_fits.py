"""
This is a DaCHS processor (http://docs.g-vo.org/DaCHS/processors.html)
to add standard headers to FITS files from the FAI 50cm Maksutov telescope.
"""

import base64
import csv
import os
import re
import sys
import tempfile
import warnings
# Suppress all warnings
warnings.filterwarnings("ignore")
from astropy.time import Time
import astropy.units as u
from astropy.coordinates import EarthLocation
from astroquery.simbad import Simbad
from astroplan.observer import Observer
from astropy.io import fits

from transliterate import translit #for observer

import pandas as pd
import numpy as np

from gavo.helpers import fitstricks
from gavo import api
from gavo.helpers import anet


##################################################
#_______________SOME INITIAL DATA________________#
##################################################

observatory= Observer(name='observatory',location=EarthLocation.from_geodetic('76d57m58.00s','43d10m36.00s'))

TELESCOPE_ENG = { #####################MAY BE WE SHOULD USE UPPER CASE TO COMPAIR VALUE WITH DICTIONARY????
  "51cmменисковыйтелескопмаксутова":
  "Wide aperture Maksutov meniscus telescope with main mirror 50 cm",
  "50cmменисковыйтелескопмаксутова":
  "Wide aperture Maksutov meniscus telescope with main mirror 50 cm",
  '50смменисковыйтелескопмаксутова':
  "Wide aperture Maksutov meniscus telescope with main mirror 50 cm",
  "большойшмидт": "Schmidt telescope (large camera)",
  "большаякамерашмидта": "Schmidt telescope (large camera)",
  "малыйшмидт": "Schmidt small camera",
  "azt-8":"AZT-8",
  "AZT-8":"AZT-8",
  None: "Provenance lost"}

METHOD_ENG = {#####################MAY BE WE SHOULD USE UPPER CASE TO COMPAIR VALUE WITH DICTIONARY
  "методметкофа": "Metkof method",
  "методметкофа-блажко":"Metkof-Blazhko method",
  "методметкофа-блажко." :"Metkof-Blazhko method",
  "методметкоф-блажко":"Metkof-Blazhko method"
}


#foclen[mm],pltsize[cm],field[deg2],mirror_diam[mm]
TELESCOPE_PARAM_DIC = { 
    "Wide aperture Maksutov meniscus telescope with main mirror 50 cm":
      [1200,[100,100],30,500],
    "Schmidt telescope (large camera)": [773,[90,120],46.6,None],
    "AZT-8": [11000,[130,160],0.25,700],
    "Unknown": [None,[None,None],None,None]}

FILTERS_ENG = {  #CHECK ON + and (10x10)
####Remove spacesand use lower case and remove dots . for checking ||| replace , and + with ;
    None:             'unknown',
    'бф':             'white filter',
    'б/ф':            'white filter',

    'бс8':            'white glass 8',

    'жс3':            'yellow glass 3',
    'жс11':           'yellow glass 11',
    'жс12':           'yellow glass 12',
    'жс14':           'yellow glass 14',
    'жс17':           'yellow glass 17',
    'жc17':           'yellow glass 17',
    'жс18':           'yellow glass 18',
    'жc18':           'yellow glass 18',
    'жс18(1)':        'yellow glass 18 (thickness=1mm)',
    'жс19':           'yellow glass 19',
    'жс20':           'yellow glass 20',
    'жс21':           'yellow glass 21',
    'жс22':           'yellow glass 22',

    'жсii':           'yellow glass II',
    'жс18(1)':        'yellow glass (thickness=1mm)',
    'жс18(10)':       'yellow glass (thickness=10mm)',

    'жф':             'yellow filter',
    'жфi':            'yellow filter I',
    'жфii':           'yellow filter II',
    'жфiii':          'yellow filter III',

    'жф3':            'yellow filter 3',
    'жф12':           'yellow filter 12',
    'жф13':           'yellow filter 13',
    'жф17':           'yellow filter 17',
    'жф18':           'yellow filter 18',
    'жф19':           'yellow filter 19',
    'жф20':           'yellow filter 20',

    'жфni':           'yellow filter I',
    'жфn1':           'yellow filter 1',
    'жфn2':           'yellow filter 2',

    'инфра-кф83':     'infrared filter 83',
    'инфра-кф84':     'infrared filter 84',
    'инфркрф84':      'infrared filter 84',

    'кфi':            'red filter I',
    'крфi':           'red filter I',
    'кфii':           'red filter II',
    'крфii':          'red filter II',
    'кфiii':          'red filter III',
    'крфiii':         'red filter III',
    'кфiii(h_alf)':   'red filter III (H_alpha)',

    'крф№kc12':       'red filter; red glass 12',
    'крфkc11-12':     'red filter; red glass 11-12',
    'kpфn3':          'red filter 3',

    'кф':             'red filter',
    'крф':            'red filter',
    'красныйфильтр':  'red filter',
    'kpфn1':          'red filter 1',
    'кф2':            'red filter 2',
    'крф№2':          'red filter 2',
    'кф№2':           'red filter 2',
    'крф№3':          'red filter 3',
    'кф№3':           'red filter 3',
    'крф№21':         'red filter 21',
    'кф№21':          'red filter 21',
    'крф№21010':      'red filter 2',
    'кф№84':          'red filter 84',
    'крф11-12':       'red filter 11-12',
    'крф14':          'red filter 14',
    'кф19':           'red filter 19',

    'кс10(10mm)':    'red glass (thickness=10mm)',
    'kc10(10mm)':    'red glass (thickness=10mm)',
    'kcns':           'red glass',
    'ксii-12':        'red glass II-12',
    'kc11-13':        'red glass 11-13',
    'kc11-14':        'red glass 11-14',
    'kc11-15':        'red glass 11-15',
    'kc11-16':        'red glass 11-16',
    'kc11-17':        'red glass 11-17',

    'kc18(10)':       'red glass (thickness=10mm)',

    'кс10':           'red glass 10',
    'кc10':           'red glass 10',
    'kc10':           'red glass 10',
    'кс11':           'red glass 11',
    'кс12':           'red glass 12',
    'kс12':           'red glass 12',
    'кс13':           'red glass 13',
    'кc13':           'red glass 13',
    'кс14':           'red glass 14',
    'кc14':           'red glass 14',
    'kc15':           'red glass 15',
    'кс11-12':        'red glass 11-12',
    'kc11-12':        'red glass 11-12',
    'кс17':           'red glass 17',
    'кc17':           'red glass 17',
    'kc17':           'red glass 17',
    'кс-17':          'red glass 17',
    'кс18':           'red glass 18',
    'kc18':           'red glass 18',
    'kс18':           'red glass 18',
    'кс19':           'red glass 19',

    'kp':             'red glass/filter',

    'ксii':           'red glass II',
    'ксiii':          'red glass III',
    'кciii':          'red glass III',
    'kcii-12':        'red glass II-12',

    'oс11':           'orange glass 11',
    'oc11':           'orange glass 11',
    'ос14':           'orange glass 14',
    'oс14':           'orange glass 14',
    'ocii':           'orange glass II',
    'ос11':           'orange glass 11',

    'с18':            'glass 18',

    'сф':             'blue filter',
    'cф':             'blue filter',
    'сф4':            'blue filter 4',
    'cф4':            'blue filter 4',

    'ссii':           'blue glass II',
    'ccii':           'blue glass II',

    'сс4':            'blue glass 4',
    'cc4':            'blue glass 4',
    'cc14':           'blue glass 14',

    'сзс':            'blue-green glass',
    'cзc':            'blue-green glass',
    'сзс-18':         'blue-green glass 18',

    'пс7':            'glass 7',

    'уфф':            'ultraviolet filter',

    'уфс':            'ultraviolet glass',
    'уфс1':           'ultraviolet glass 1',
    'уфс2':           'ultraviolet glass 2',
    'уфс3':           'ultraviolet glass 3',
    'уфс-3':          'ultraviolet glass 3',
    'уфс350':         'ultraviolet glass 350',
    'уфс4':           'ultraviolet glass 4',

    'фс5':            'violet glass 5',
    'фс6':            'violet glass 6',
    'фc6':            'violet glass 6',
    'фс7':            'violet glass 7',
    'фс8':            'violet glass 8',
    'фс9':            'violet glass 9',

    'синийфильтршотта':       'blue Schott filter',
    'сфшотта':                'blue Schott filter',
    'cфшотта':                'blue Schott filter',
    'зфшотта':                'green Schott filter',
    'уфс-2(фильтршотта)':     'ultraviolet glass 2 (Schott filter)',
    'уфшотта':                'ultraviolet Schott filter',
    'уффшотта':               'ultraviolet Schott filter',
    'уфсшотта':               'ultraviolet Schott glass',
    'фшотта':                 'Schott filter',
    'фhalfa':                 'H_alpha filter',
    'h_alf':                  'H_alpha',
    'h_alpha':                'H_alpha',

    'стекло':                 'glass',
    'поляроид':               'polaroid (polarization)' ,
    'поляроид':               'polaroid (polarization)' ,
    'прозрачный':             'transparent' ,
    'объективнаяпризма':      'objective prism',
    'вращающаясядиафрагма':   'rotating diaphragm',
    'agfan83(ик)':            'Agfan 83 (Infrared)',

    'интефериционныйфильтр№2на': 'interference filter 2 (H_alpha)',
}


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~OBJECT NAME~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

def get_objtype_cards(raw_objtype):
  """
  returns dictionary of keyword-value pairs for the FITS headers for our raw objects list

  """

  objtype=raw_objtype.split(";")
  if len(objtype)==1:
    return {"OBJTYPE": objtype[0]}
  else:
    retval = {"OBJTYPE": objtype[0]}
    retval.update(dict(
      (f"OBJTYPE{n+1}",val) for n,val in enumerate(objtype)))
    return retval

def get_filters_cards(filters):
  """
  returns dictionary of keyword-value pairs for the FITS headers for filters list

  >>> get_filters_cards(["name"])
  {'FILTER': 'name'}
  >>> get_filters_cards(["name1","name2"])
  {'FILTER': 'name1', 'FILTER1': 'name1', 'FILTER2': 'name2'}
  """

  if len(filters)==1:
    return {"FILTER": filters[0]}
  else:
    retval = {"FILTER": filters[0]}
    retval.update(dict(
      (f"FILTER{n+1}",val) for n,val in enumerate(filters)))
    return retval


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~COORDINATES~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

DEC_FORMATS = [re.compile(pat) for pat in [
    r"(?P<sign>-?)(?P<degrees>\d+\.?\d*)$",
    r"(?P<sign>-?)((?P<degrees>\d+) (?P<minutes>\d+\.?\d*))$",
    r"(?P<sign>-?)(?P<degrees>\d+) (?P<minutes>\d+)(?: (?P<seconds>\d+(?:.\d+)?))?$",
    r"(?P<sign>-?)((?P<degrees>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:.\d+)?))$",
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
    #print("dec ", raw_dec)
    if not raw_dec:
      return None
    try:
      raw_dec = raw_dec.strip().replace("+","")
    except AttributeError:
      print("raw_dec ",raw_dec)
    if ":" in raw_dec:
      raw_dec = raw_dec.replace(":", " ")

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

def reformat_single_dec(raw_dec):
    """
    returns declination in the format "dd:mm:ss".

    >>> reformat_single_dec("29.06")
    '+29:03:36'
    >>> reformat_single_dec("-23.30")
    '-23:18:00'
    >>> reformat_single_dec("50 41 45")
    '+50:41:45'
    >>> reformat_single_dec("-01 28 02")
    '-01:28:02'
    >>> reformat_single_dec("-01 28")
    '-01:28:00'
    """
    return api.degToDms(
        dec_to_deg(raw_dec),
        sepChar=":", secondFracs=0,
        preserveLeading=True)

def reformat_dec(raw_dec):
    """
    returns declination in the format "dd:mm:ss".

    >>> reformat_dec("29.06;-23.30")
    ['+29:03:36', '-23:18:00']
    >>> reformat_dec("50 41 45")
    ['+50:41:45']
    >>> reformat_dec("-01 28")
    ['-01:28:00']
    """
    raw_dec = raw_dec.split(";")
    return [reformat_single_dec(dec) for dec in raw_dec]

RA_FORMATS = [re.compile(pat) for pat in [
    r"(?P<hours>\d+) (?P<minutes>\d+)(?: (?P<seconds>\d+(?:.\d+)?))?$",
    r"(?P<hours>\d+)h(?P<minutes>\d+(?:\.\d+)?)m(?:(?P<seconds>\d+)s)?$",
    r"(?P<hours>\d+)h(?P<minutes>\d+(?:m?\.\d+)?)(?:(?P<seconds>\d+)s)?$",
    r"(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+(?:.\d+)?)$",
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
    #print("ra ", raw_dec)
    if not raw_ra:
      return None

    try:
      raw_ra = raw_ra.strip()
    except AttributeError:
      print("raw_ra ",raw_ra)
    if ":" in raw_ra:
      raw_ra = raw_ra.replace(":", " ")

    for pattern in RA_FORMATS:
        mat = re.match(pattern, raw_ra)
        if mat:
            break
    else:
        raise ValueError(f"Not a valid RA {raw_ra}")

    parts = mat.groupdict()
    hours = (float(parts["hours"])
        + float(parts["minutes"].replace("m",""))/60.
        + float(parts["seconds"] or 0)/3600.)
    return hours/24*360

def reformat_single_ra(raw_ra):
    """
    returns right ascension in the format "hh:mm:ss"

    >>> reformat_single_ra("05 32 49")
    '05:32:49'
    >>> reformat_single_ra("05h33m")
    '05:33:00'
    >>> reformat_single_ra("02h41m45s")
    '02:41:45'
    >>> reformat_single_ra("01 28")
    '01:28:00'
    >>> reformat_single_ra("12h")
    Traceback (most recent call last):
    ValueError: Not a valid RA 12h
    """
    return api.degToHms(ra_to_deg(raw_ra), sepChar=":", secondFracs=0)

def reformat_ra(raw_ra):
    """
    returns right ascension in the format "hh:mm:ss"

    >>> reformat_ra("05 32 49;05h33m")
    ['05:32:49', '05:33:00']
    >>> reformat_ra("02h41m45s;01 28")
    ['02:41:45', '01:28:00']
    >>> reformat_ra("12h")
    Traceback (most recent call last):
    ValueError: Not a valid RA 12h
    """
    raw_ra = raw_ra.split(";")
    return [reformat_single_ra(ra) for ra in raw_ra]

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~EXPOSURE~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def parse_single_exposure(raw_time):
    """returns seconds of time for an h-m-s time string.

    Here is the syntax supported by the function.

    >>> parse_single_exposure("1h")
    3600.0
    >>> parse_single_exposure("4h30m")
    16200.0
    >>> parse_single_exposure("1h30m20s")
    5420.0
    >>> parse_single_exposure("20m")
    1200.0
    >>> parse_single_exposure("10.5m")
    630.0
    >>> parse_single_exposure("1m10s")
    70.0
    >>> parse_single_exposure("15s")
    15.0
    >>> parse_single_exposure("s23m")
    Traceback (most recent call last):
    ValueError: Cannot understand time 's23m'
    """
    try:
      raw_time.replace(" ","")
    except AttributeError:
      print("raw_time ",raw_time)
    mat = re.match(
        r"^(?P<hours>\d+(?:\.\d+)?h)?"
        r"(?P<minutes>(\d+m)?(?:\d+\.\d+m)?(?:\d+m\.\d+)?)?"
        r"(?P<seconds>\d+(?:\.\d+)?s?)?$", raw_time.replace(" ",""))
    if mat is None:
        raise ValueError(f"Cannot understand time '{raw_time}'")
    parts = mat.groupdict()
    return (float((parts["hours"] or "0h").replace('h',''))*3600
        + float((parts["minutes"] or "0m").replace("m",""))*60
        + float((parts["seconds"] or "0s").replace('s','')))

def parse_exposure_times(raw_time):
    """
    returns a list of floats giving the exposure times encoded in raw_exp_times.

    This is a ;-separated list of individual items.    see parse_single_exposure for
    details on the format.
    >>> parse_exposure_times("1h;2h;3h")
    [3600.0, 7200.0, 10800.0]
    >>> parse_exposure_times("1h30m20s;2h20m10s")
    [5420.0, 8410.0]
    >>> parse_exposure_times("1h30m20s;h20m10s")
    Traceback (most recent call last):
    ValueError: Cannot understand time 'h20m10s'
    """
    try:
      raw_time.replace(" ","")
    except AttributeError:
      print("raw_time1 ",raw_time)
    return [parse_single_exposure(r_t.replace(" ",""))
        for r_t in raw_time.split(";")]

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

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~TIME OBS~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TIME_FORMATS = [re.compile(pat) for pat in [
    r"(?P<hours>\d+)h$",
    r"(?P<hours>\d+\.h\d+)$",
    r"(?P<hours>\d+)h(?P<minutes>\d+)m?$",
    r"(?P<hours>\d+)h(?P<minutes>\d+(?:\.\d+)?)m?$",
    r"(?P<hours>\d+)h(?P<minutes>\d+(?:m?\.\d+)?)$",
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

    try:
      raw_time.replace(" ","")
    except AttributeError:
      print("raw_time2 ",raw_time)
    raw_time = raw_time.replace(" ","")
    for pattern in TIME_FORMATS:
        mat = re.match(pattern, raw_time)
        if mat:
            break
    else:
        raise ValueError(f"Not a valid time {raw_time}")

    parts = mat.groupdict()
    hours = (float(parts.get("hours", '0h').replace('h', ''))
        + float(parts.get("minutes", '0m').replace('m', ''))/60.
        + float(parts.get("seconds", '0s').replace('s',''))/3600.)

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
    if raw_times==raw_times and raw_times!=None:
        return [reformat_single_time(time) for time in raw_times.split(";")]
    else:
        return None



#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~TIME ORIG~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def get_time_start_cards(raw_times, time_format):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local sidereal time of end of observations.

  >>> get_time_start_cards("1h23m12s", "LT ")
  {'TMS-ORIG': 'LT 01:23:12'}
  >>> get_time_start_cards("13h23m;5h13;12h15m54s", "LST ")
  {'TMS-ORIG': 'LST 13:23:00', 'TMS-OR1': 'LST 13:23:00', 'TMS-OR2': 'LST 05:13:00', 'TMS-OR3': 'LST 12:15:54'}
  """
  times = reformat_time(raw_times)
  if len(times)==1:
    return {"TMS-ORIG": f"{time_format}{times[0]}"}
  else:
    retval = {"TMS-ORIG": f"{time_format}{times[0]}"}
    retval.update(dict(
      (f"TMS-OR{n+1}", f"{time_format}{val}") for n, val in enumerate(times)))
    return retval

def get_time_end_cards(raw_times, time_format):
  """
  returns dict of keyword-value pairs for the FITS headers for our raw
  local sidereal time of end of observations.

  >>> get_time_end_cards("1h23m12s", "LT ")
  {'TME-ORIG': 'LT 01:23:12'}
  >>> get_time_end_cards("13h23m;5h13;12h15m54s", "LST ")
  {'TME-ORIG': 'LST 13:23:00', 'TME-OR1': 'LST 13:23:00', 'TME-OR2': 'LST 05:13:00', 'TME-OR3': 'LST 12:15:54'}
  """
  times = reformat_time(raw_times)
  if len(times)==1:
    return {"TME-ORIG": f"{time_format}{times[0]}"}
  else:
    retval = {"TME-ORIG": f"{time_format}{times[0]}"}
    retval.update(dict(
      (f"TME-OR{n+1}", f"{time_format}{val}") for n, val in enumerate(times)))
    return retval

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~DATE OBS~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def expand_date(raw_date):
    """
    Inserts a 19 in front of the year part of a d.m.y raw_date if we
    sense a two-digit year and inserts 0 in front of date/month part
    if there is one digit date

    >>> expand_date("30.x1.29")
    '30.x1.1929'
    >>> expand_date("30.x1.1929")
    '30.x1.1929'
    >>> expand_date("3.2.98")
    '03.02.1998'
    >>> expand_date("13.2.98")
    '13.02.1998'
    >>> expand_date("3.12.1998")
    '03.12.1998'
    """
    date_split = raw_date.split(".")
    if len(date_split[0])==1:
        date_split[0] = f'0{date_split[0]}'
    if len(date_split[1])==1:
        date_split[1] = f'0{date_split[1]}'
    if len(date_split[-1])==2:
        date_split[-1] = f'19{date_split[-1]}'
    return f'{date_split[0]}.{date_split[1]}.{date_split[2]}'

def parse_one_date(raw_date):
    """
    Returns the first part of a date or date interval.

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
    ##print("interval ", interval)
    if len(interval)==1:#one date 13.10.1968
        start_parts = interval[0].split(".") #["13","10","1968"]
    else: #few dates 12-13.10.1968
        # complete the start date from parts of the end date
        end_day, end_month, end_year = interval[1].split(".")
        try:
          start_parts = interval[0].strip().split(".")
        except AttributeError:
          print("start_parts ", start_parts) 
        if len(start_parts)==1: #one month 12-13.10.1968
          start_parts.extend([end_month, end_year])
        elif len(start_parts)==2: #two month 31.05-01.06.1978
          start_parts.append(end_year)
        elif len(start_parts)==3: #two month 31.05.-01.06.1978
          if start_parts[-1]=="":
            start_parts = start_parts[:2]
            start_parts.append(end_year) 
        #if there is len = 3 (31.12.1987-01.01.1988)
        #the first values will be remembered

    start_date = ".".join(start_parts)
    return expand_date(start_date)

def parse_date_list(raw_dates):
    """
    Returns evening date of observations.

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


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~DATE OBS~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_sid_delta(dates, sid_times):
  """
  Returns delta (hours, float) list for sidereal times.
  Delta between midnight and obs time.

  dates -- list of obs dates from obs log ["31.12.1989","01.01.1990"]
  sid_times -- list of SIDEREAL obs times from obs log, XX.XX hours (hh:mm:ss or floats)

  >>> get_sid_delta(["31.12.1989","01.01.1990"],[7.45,7.56])
  [1.7090326129862063, 1.7530447602092671]
  >>> get_sid_delta(["08.02.1964"], ["3:15:00","3:30:00"])
  [-5.007863908919145]
  """
  longitude = longitude = (76+57/60+57/3600)*u.degree # longitude of Kamenskoye Plato Observatory
  coef = 24/(23+56/60+4/3600)
  delta_initial = 6*coef
  dates_ymd = []
  #we have to rewrite dates from DD.MM.YYYY format to YYYY-MM-DD format
  for i in range(0,len(dates)):
    if "." in dates[i]:
      d = dates[i].split(".")
      dates_ymd.append(f"{d[2]}-{d[1]}-{d[0]}".replace(" ",""))

  if len(dates) == 1:
    lst_mid = (Time(f"{dates_ymd[0]} 00:00:00").sidereal_time('mean',longitude=longitude).value - delta_initial)%24
    return [get_one_sid_delta(lst_mid,sid_times[0])]

  elif len(dates) == 2:
    lst_mid_1 = (Time(f"{dates_ymd[0]} 00:00:00").sidereal_time('mean',longitude=longitude).value - delta_initial)%24
    lst_mid_3 = (Time(f"{dates_ymd[1]} 00:00:00").sidereal_time('mean',longitude=longitude).value - delta_initial)%24
    return [get_one_sid_delta(lst_mid_1,sid_times[0]),get_one_sid_delta(lst_mid_3,sid_times[1])]


def get_one_sid_delta(lst_mid,sid_time):
    """
    Returns delta in parts of hour between midnight time and
    time from observational log.
    Delta is positive if observation was made after midnight
    and negative if before.
    lst_mid -- local sidereal time XX.XX hours (floats!)
    sid_time -- obs sidereal time XX.XX hours (hh:mm:ss or floats)

    >>> "{:.5f}".format(get_one_sid_delta(13,"17:00:00"))
    '4.00000'
    >>> "{:.5f}".format(get_one_sid_delta(1,23))
    '2.00000'
    >>> "{:.5f}".format(get_one_sid_delta(1,4))
    '3.00000'
    >>> "{:.5f}".format(get_one_sid_delta(15,10))
    '5.00000'
    """

    if ":" in str(sid_time):
        sid_time  = api.dmsToDeg(sid_time, ":")%24
    if lst_mid>=0 and lst_mid<=12:

        if sid_time>=12 and sid_time<24:

            delta = lst_mid - sid_time

            if abs(delta) > 8 and abs(delta) < 24: #before mid
                delta = 24 % abs(delta)
            elif abs(delta) > 24:
                delta = abs(delta) % 24

            else: #after mid
                delta = delta

        elif sid_time>=0 and sid_time<=12:#before
            delta = -(lst_mid - sid_time)

    elif lst_mid>=12 and lst_mid<24:

        if sid_time>=12 and sid_time<24:#before
            delta = -(lst_mid - sid_time)

        elif sid_time>=0 and sid_time<=12:
            delta = sid_time - lst_mid

            if abs(delta) > 8: #after mid
                delta = delta%24
            else:  #before mid
                delta = -delta

   # coef = 24/(23+56/60+4/3600)   # because sidereal time not equal usual time. it is 23:56:04, not 24 hour

    return delta#*coef


def get_lt_from_st(dates, sid_times):
  """
  Returns local date-time FUNCTION of observation from sidereal time
  and doesn't take into accaunt real delta between
  UT and local time (DLS and DT).

  dates -- list of obs dates from obs log
  sid_times -- list of SIDEREAL obs times from obs log ["hh:mm:ss"]

  >>> get_lt_from_st(["09.02.1989"], ["10:24:06"])
  [<Time object: scale='utc' format='iso' value=1989-02-10 02:00:58.509>]
  >>> get_lt_from_st(["14.09.1964","15.09.1964"], ["01:24:06","20:42:06"])
  [<Time object: scale='utc' format='iso' value=1964-09-15 02:45:12.063>, <Time object: scale='utc' format='iso' value=1964-09-15 21:59:15.508>]
  """

  delta_i = get_sid_delta(dates, sid_times) #list. may contain 1 or 2 elements
  #we have to rewrite dates from DD.MM.YYYY format to YYYY-MM-DD format
  dates_ymd = []
  for i in range(0,len(dates)):
    if "." in dates[i]:
      d = dates[i].split(".")
      dates_ymd.append(f"{d[-1]}-{d[1]}-{d[0]}")

  if len(dates_ymd) == 1: #given date is date of beginning of whole night obeservations
    return [Time(f"{dates_ymd[0]} 00:00:00") + 1*u.day + delta_i[0]*u.hour] #so we add 1 day, because we need midnight
    #of observational night (for more info see parse_date_list function because dates goes from there)

  elif len(dates_ymd) == 2:
    return [Time(f"{dates_ymd[0]} 00:00:00") + 1*u.day + delta_i[0]*u.hour,Time(f"{dates_ymd[1]} 00:00:00") + 1*u.day + delta_i[1]*u.hour]


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~CHECK SUN AND ALTITUDE~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_object_altitude(dec,phi,hour_angle):
  """

  Returns altitude of object in degrees (float)

  dec -- [float, deg] declanation of object
  phi -- [float, deg] latitud of observatory
  hour_angle -- [float, deg] hour angle of object (LST-RA)

  >>> "{:.5f}".format(get_object_altitude(-29.5596111111111111,43.17666666666666,21.40750000000000003))
  '14.65550'
  >>> "{:.5f}".format(get_object_altitude(8.869166666666667,43.17666666666666,1.041111111111111))
  '55.68041'

  """
  return 90 - np.arccos(np.sin(phi*u.degree)*np.sin(dec*u.degree)+np.cos(phi*u.degree)*np.cos(dec*u.degree)*np.cos(hour_angle*u.degree)).to_value("degree")

def sun_set_rise_time(date,observatory):
  """
  Returns sunset and sunrise time for observational point
  Sometimes function define wrong date of sunset/sunrise
  because parameters ("next","near","previous") are not
  universal.

  date -- time function
  observatory -- astroplan object with neccessary data about observatation place

  >>> sun_set_rise_time(Time("1987-08-12 00:00:00"),observatory= Observer(name='observatory',location=EarthLocation.from_geodetic('76d57m58.00s','43d10m36.00s')))
  (<Time object: scale='utc' format='jd' value=2447019.3312281347>, <Time object: scale='utc' format='jd' value=2447019.748774269>)
  >>> sun_set_rise_time(Time("1964-01-23 00:00:00"),observatory= Observer(name='observatory',location=EarthLocation.from_geodetic('76d57m58.00s','43d10m36.00s')))
  (<Time object: scale='utc' format='jd' value=2438417.2391776997>, <Time object: scale='utc' format='jd' value=2438417.8487855475>)
  """

  if Time(f"{date.iso[:10]} 00:00:00")-date < 30*u.second:
    date = Time(f"{date.iso[:10]} 00:00:00")

  sunset = observatory.sun_set_time(date, which='previous')+6*u.hour
  delta = date.datetime.day - sunset.datetime.day
  if delta != 1 and delta < 27 and delta > 30: # also check for end of month (28,29,30,31)
    sunset =observatory.sun_set_time(date, which='nearest')+6*u.hour
    delta = date.datetime.day - sunset.datetime.day
    if delta != 1 and delta < 27 and delta > 30: # also check for end of month (28,29,30,31)
      raise ValueError(f"Cannot define sunset time for {date.iso} -- {sunset}")

  try:
    sunrise = observatory.sun_rise_time(date, which='nearest')+6*u.hour
  except TypeError:
    sunrise = observatory.sun_rise_time(date, which='previous')+6*u.hour
  # print("sunrise ", sunrise)

  sunrise = sunrise.flatten()[0] #somewhy sometimes becomes an array

  delta = date.datetime.day - sunrise.datetime.day
  if date.datetime.day - sunrise.datetime.day != 0:
    sunrise = observatory.sun_rise_time(date, which='next')+6*u.hour
    delta = date.datetime.day - sunrise.datetime.day
    if date.datetime.day - sunrise.datetime.day != 0:
      raise ValueError(f"Cannot define sunset time for {date.iso} -- {sunset}")

  return sunset, sunrise


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~DATE-TIME UT~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def get_delta_real(date):

  """
  Returns true delta (float, hours)
  date - time function of date of observ

  >>> get_delta_real(Time("1964-08-13 00:00:00.000"))
  <Quantity 6. h>
  >>> get_delta_real(Time("1984-03-25 03:45:54.000"))
  <Quantity 7. h>

  """
  sunday = Time("2022-05-01 00:00:00")
  y = date.datetime.year#year of observation
  m = date.datetime.month#month of observation
  d = date.datetime.day#day of observation
  hour = date.datetime.hour#day of observation

  if y >= 1981 and y < 1991:
      if m == 3:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta=7*u.hour
                  else:
                      delta= 6*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                      continue
                  else:
                      if date < t:
                          delta = 6*u.hour
                      else:
                          delta = 7*u.hour

          else:
              delta = 6*u.hour

      elif m == 9:
          if d >=24 and d <= 30:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 6*u.hour
                  else:
                      delta = 7*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                      continue
                  else:
                      if date < t:
                          delta = 7*u.hour
                      else:
                          delta = 6*u.hour
          else:
              delta = 7*u.hour

      elif m > 3 and m < 9:
          delta = 7*u.hour
      else:
          delta = 6*u.hour

  elif y == 1991:
      if m == 3:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 6*u.hour
                  else:
                      delta = 5*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 5*u.hour
                      else:
                          delta = 6*u.hour
          else:
              delta = 5*u.hour

      elif m == 9:
          if d >=24 and d <= 30:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 5*u.hour
                  else:
                      delta = 6*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 6*u.hour
                      else:
                          delta = 5*u.hour
          else:
              delta = 6*u.hour

      elif m > 3 and m < 9:
          delta = 6*u.hour
      else:
          delta = 5*u.hour

  elif y == 1992:
      if m == 1:
          if d <19:
              delta = 5*u.hour
          else:
              delta = 6*u.hour

      elif m == 3:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 7*u.hour
                  else:
                      delta = 6*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 6*u.hour
                      else:
                          delta = 7*u.hour
          else:
              delta = 6*u.hour

      elif m == 9:
          if d >=24 and d <= 30:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 6*u.hour
                  else:
                      delta = 7*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 7*u.hour
                      else:
                          delta = 6*u.hour
          else:
              delta = 7*u.hour

      elif m > 3 and m < 9 and m!=1:
          delta = 7*u.hour
      else: #2,10,11,12
          delta = 6*u.hour

  elif y >= 1993 and y < 1996:
      if m == 3:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 7*u.hour
                  else:
                      delta = 6*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 6*u.hour
                      else:
                          delta = 7*u.hour
          else:
              delta = 6*u.hour

      elif m == 9:
          if d >=24 and d <= 30:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 6*u.hour
                  else:
                      delta = 7*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 7*u.hour
                      else:
                          delta = 6*u.hour
          else:
              delta = 7*u.hour

      elif m > 3 and m < 9:
          delta = 7*u.hour
      else:
          delta = 6*u.hour

  elif y >= 1996 and y < 2005:
      if m == 3:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 7*u.hour
                  else:
                      delta = 6*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 6 *u.hour
                      else:
                          delta = 7*u.hour
          else:
              delta = 6*u.hour

      elif m == 10:
          if d >=25 and d <= 31:
              modulo = (date - sunday).value%7
              if modulo < 1:
                  if int(hour) >= 3:
                      delta = 6*u.hour
                  else:
                      delta = 7*u.hour
              else:
                  t = Time(f"{y}-{m}-23 00:00:00")
                  modulo = 2
                  while modulo >= 1:
                      t = t + 1*u.day
                      modulo = (t - sunday).value % 7
                  else:
                      if date < t:
                          delta = 7*u.hour
                      else:
                          delta = 6*u.hour
          else:
              delta = 7*u.hour

      elif m > 3 and m < 10:
          delta = 7*u.hour
      else:
          delta = 7*u.hour
  elif y <=1980 or y >= 2005:
      delta = 6*u.hour

  return delta

def convert_local_date_time_UT(dates, obs_times):
  """
  Returns list of local observational time in UT in fits format.
  It takes into accaunt real delta.

  Will be used for headers only, may be additional column

  dates -- list of obs dates from obs log
  obs_times -- list observational time given in obs log

  >>> convert_local_date_time_UT(["14.09.1964","15.09.1964"], ["01:24:06","20:42:06"])
  ['1964-09-14T19:24:05.999', '1964-09-16T14:42:05.999']
  >>> convert_local_date_time_UT(["25.03.1984"], ["04:24:06"])
  ['1984-03-25T21:24:06.000']

  """
  obs_times_hms = []
  for i in range(0,len(obs_times)):
    #conversation hh:mm:ss to XX.XX
    obs_time = api.dmsToDeg(obs_times[i], ":")%24 #%24 because somewhere we have time like 24:05:30
    obs_times_hms.append(api.hoursToHms(obs_time))
  dates_ymd = []
  #we have to rewrite dates from DD.MM.YYYY format to YYYY-MM-DD format
  for i in range(0,len(dates)):
    d = dates[i].split(".")
    dates_ymd.append(f"{d[2]}-{d[1]}-{d[0]}".replace(" ",""))
  if len(dates_ymd) == 1:
    date_time = Time(f"{dates_ymd[0]} {obs_times_hms[0]}") + 1*u.day #+1day because in our dates list
    #we have only first date of obs (for more info see parse_date_list function)
    delta_real = get_delta_real(date_time)
    return [(date_time - delta_real).fits]

  elif len(dates_ymd) == 2:
    date_time_1 = Time(f"{dates_ymd[0]} {obs_times_hms[0]}") + 1*u.day
    if len(obs_times_hms) < 4:
      date_time_2 = Time(f"{dates_ymd[1]} {obs_times_hms[1]}") + 1*u.day
    elif len(obs_times_hms) == 4:
      date_time_2 = Time(f"{dates_ymd[1]} {obs_times_hms[3]}") + 1*u.day
    delta_real_1 = get_delta_real(date_time_1)
    delta_real_2 = get_delta_real(date_time_2)
    return [(date_time_1 - delta_real_1).fits,(date_time_2 - delta_real_2).fits]


def dmsToDeg(dms,splitter=":"):
  """
  Convert degrees:minutes:seconds format
  to degree values.

  >>> dmsToDeg("-54:26:30",splitter=":")
  -54.44167
  >>> dmsToDeg("14:15:00",splitter=":")
  14.25
  """
  try:
    dms_s = dms.replace("-","").split(splitter)
  except AttributeError:
    print("dms_s ", dms_s)
  deg = float(dms_s[0]) + float(dms_s[1])/60 + float(dms_s[-1])/3600
  if "-" in dms:
    return round(-deg,5)
  else:
    return round(deg,5)

def hoursToHms(hours):
  """
  Convert hours to
  hours:minutes:seconds format.

  >>> hoursToHms(12.5)
  '12:30:00'
  >>> hoursToHms(2.2)
  '02:12:00'
  """
  hours = hours%24 #because could be 24.05
  h = int(hours)
  mi = (hours - h)*60
  m = int(mi)
  se = (mi - m)*60
  s = int(se)
  if h<10:
    h = f"0{h}"
  if m<10:
    m = f"0{m}"
  if s<10:
    s = f"0{s}"

  return f"{h}:{m}:{s}"

def degToHms(deg):
  """
  Convert degrees to hours and to
  hours:minutes:seconds format.

  >>> degToHms(352.6)
  '23:30:24'
  >>> degToHms(12.4)
  '00:49:36'
  """
  hours = abs(deg) * 24 / 360
  return hoursToHms(hours)

def degToDms(deg):
  """
  Convert degrees to
  degrees:minutes:seconds format.

  >>> degToDms(52.41)
  '52:24:35'
  >>> degToDms(-148.56)
  '-148:33:36'
  """
  if deg<0:
    deg = abs(deg)
    sign = "-"
  else:
    sign = ""
  d = int(deg)
  mi = (deg - d)*60
  m = int(mi)
  se = (mi - m)*60
  s = int(se)
  if d<10:
    d = f"0{d}"
  if m<10:
    m = f"0{m}"
  if s<10:
    s = f"0{s}"

  return f"{sign}{d}:{m}:{s}"

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~TTEESSTT~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def run_tests(*args):
  """
  runs all doctests and exits the program.
  """
  import doctest
  sys.exit(doctest.testmod()[0])

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~HEADER CLASS~~~~~~~~~~~~~~~~~~~~
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

class PAHeaderAdder(api.AnetHeaderProcessor):
  indexPath = "/usr/share/astrometry" #path to indexes
  sp_total_timelimit = 180 #maximum time for field solving
  sp_lower_pix = 3 #the smallest permissible pixel size in arcsecs
  sp_upper_pix = 6 #the largest permissible pixel size in arcsecs
  sp_endob = 100 # last object to be processed
  sp_indices = ["index-41[01]*.fits"]# The file names from anet’s index directory you want to have used

  sourceExtractorControl = """
    DETECT_MINAREA   20
    DETECT_THRESH    5
    SEEING_FWHM      1.2
  """#DETECT_MINAREA 20 (IDK)
  #DETECT_THRESH 5 (SIGNAL 5SIGMA ABOVE THE NOISE IS SOURSE)
  #SEEING_FWHM 1.2 (IDK)

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)  # Вызов конструктора родительского класса
    self.fits_file = None  # Добавление своей переменной
    self.fits_name = None  # Добавление своей переменной

  @staticmethod
  def addOptions(optParser):
    api.AnetHeaderProcessor.addOptions(optParser)
    optParser.add_option("--test", help="Run unit tests, then exit",
      action="callback", callback=run_tests)

  def _createAuxiliaries(self, dd):
    log_path = os.path.join(dd.rd.resdir, "/var/gavo/inputs/logbook_archival", "logbook.csv")
    with open(log_path, "r", encoding="utf-8") as f:
      rdr = csv.DictReader(f, delimiter=",")
      self.platemeta = dict((rec["ID"].lower().replace("с","c"), rec) for rec in rdr)
      #identification by identification number
  
  def NOobjectFilter(self, inName):
    """throws out funny-looking objects from inName as well as objects
    near the border.
    """
    

    width = max(data_fits.field("X_IMAGE"))
    height = max(data_fits.field("Y_IMAGE"))
    badBorder = 0.2
    data_fits = data_fits[data_fits.field("ELONGATION")<1.2]
    data_fits = data_fits[data_fits.field("X_IMAGE")>width*badBorder]
    data_fits = data_fits[data_fits.field("X_IMAGE")<width-width*badBorder]
    data_fits = data_fits[data_fits.field("Y_IMAGE")>height*badBorder]
    data_fits = data_fits[data_fits.field("Y_IMAGE")<height-height*badBorder]

    # the extra np.array below works around a bug in several versions
    # of pyfits that would write the full, not the filtered array
    hdu = api.pyfits.BinTableHDU(np.array(data_fits))
    hdu.writeto("foo.xyls")
    hdulist.close()
    os.rename("foo.xyls", inName)

  def _shouldRunAnet(self, srcName, header):
    #try:
    if "-st" in srcName or "Cal" in srcName:
      return True
    else:
      return True #True for all files findme
    #except gavo.helpers.processing.CannotComputeHeader as e:
        # Handle CannotComputeHeader exception (astrometry failure)
        #print(f"Astrometry failed for {srcName}: {e}")
        # Optionally, log the error or take other actions if needed.

    #except Exception as e:
        # Handle other exceptions that may occur during astrometry or header modification
    #    print(f"An error occurred for {srcName}: {e}")
        # Optionally, log the error or take other actions if needed.

  def _isProcessed(self, srcName):
    hdr = self.getPrimaryHeader(srcName)
    self.fits_file = fits.open(srcName)
    if "/" in srcName: 
      self.fits_name = srcName.split("/")[-1].replace("–","-").encode("utf-8").decode("utf-8") 
      print(self.fits_name)
    return "RA-ORIG" in hdr and "A_ORDER" in hdr

  def _mungeHeader(self, srcName, hdr):
    plateid = srcName.split(".")[-2].split("_")[-1].lower().replace("с","c")
    print(plateid)
    data = self.platemeta[plateid]
    
    thismeta = data

    objtype = data["OBJTYPE"] #we will add the column with data later
    try:
      for k,v in data.items():
        if isinstance(v, str) and (v == " " or v == "  " or v == ""):
          data[k] = None
    except AttributeError:
      print("AttributeError data")


    #if some columns are renamed it is easier to fix it here
    #and in the end when we are saving table
    plate_id  = data["ID"]
    obj_name  = data["OBJECT"]
    ra        = data["RA"]
    dec       = data["DEC"]
    date_obs  = data["DATE-OBS"]
    exptime   = data["EXPTIME"]
    tms_lst   = data["TMS-LST"]
    tme_lst   = data["TME-LST"]
    tms_lt    = data["TMS-LT"]
    tme_lt    = data["TME-LT"]
    telescope = data["TELESCOPE"]
    observer  = data["OBSERVER"]
    emulsion  = data["EMULSION"]
    method    = data["METHOD"]
    size      = data["SIZE"]
    filters   = data["FILTER"]
    obj_type  = data["OBJTYPE"]
    focus     = data["FOCUS"]
    platenotes= data["PLATNOTE_en"]
    scannotes = data["SCANNOTE_en"]
    obsnotes  = data["OBSNOTE_en"]
    notes     = data["NOTES_en"]
    skycond   = data["SKYCOND_en"]

    #~~~~~~~~~~~~~~~~~~~COORDINATES~~~~~~~~~~~~~~~~~~~~~~
    #~~~~~~~~~SIMBAD-QUERY~~~~~~~~~
    ra_simbad = []
    dec_simbad = []
    for obj in obj_name.replace(",",";").split(";"):
      simbad_table = Simbad.query_object(obj)
      if simbad_table:#if object data there is in Simbad
        ra_simbad.append(":".join(simbad_table["RA"].data[0].split(" ")))
        dec_simbad.append(":".join(simbad_table["DEC"].data[0].split(" ")))
      else:#if not
        ra_simbad.append(None)
        dec_simbad.append(None)

    ra_simbad = [ra_s for ra_s in ra_simbad if str(ra_s) != 'nan']
    dec_simbad = [dec_s for dec_s in dec_simbad if str(dec_s) != 'nan']

    if len(ra_simbad)==0:
      ra_simbad = None
      dec_simbad = None

    #~~~~~~~~~COORDS EDITED~~~~~~~~~
    if ra==ra and ra!=None:#if there is data in obs log
      if ra=="" or ra==" " or ra=="  ":
        ra_edit = None#there is no data in neither obs log or Simbad
      else:
        ra_edit = reformat_ra(ra) # hh:mm:ss
    else:#if there is no data in obs log
      if ra_simbad == ra_simbad:#if there is data in Simbad
        ra_edit = ra_simbad#list of hh:mm:ss format ra
      else:#if there is not data in Simbad
        ra_edit = None#there is no data in neither obs log or Simbad
    if dec == dec and dec!=None:#if there is data in obs log
      if dec=="":
        dec_edit = None#there is no data in neither obs log or Simbad
      else:
        dec_edit = reformat_dec(dec) # dd:mm:ss
    else:#if there is no data in obs log
      if dec_simbad == dec_simbad:#if there is data in Simbad
        dec_edit=dec_simbad#list of hh:mm:ss format ra
      else:#if there is not data in Simbad
        dec_edit = None#there is no data in neither obs log or Simbad
    if dec_edit:
      dec_deg = dec_to_deg(dec_edit[0])
    else:
      decdeg = None
    if ra_edit:
      ra_deg = ra_to_deg(ra_edit[0])
    else:
      ra_deg = None


    #~~~~~~~~~~~~~~~~~~~DATE AND TIME ORIG~~~~~~~~~~~~~~~~~~~~~~

    tms_lt_edit  = None
    tme_lt_edit  = None
    tms_lst_edit = None
    tme_lst_edit = None

    if tms_lt:
      tms_lt_edit=reformat_time(tms_lt)
    if tme_lt:
      tme_lt_edit=reformat_time(tme_lt)
    if tms_lst:
      tms_lst_edit=reformat_time(tms_lst)
    if tme_lst:
      tme_lst_edit=reformat_time(tme_lst)

    if tms_lt_edit:
      obs_times = tms_lt_edit
    else:
      obs_times = tms_lst_edit #then lst or None

    if date_obs == date_obs and date_obs!=None:
      date_obs_orig = parse_date_list(date_obs) #returns first date (12-13.02.1987 --> 12.02.1987)

    else:
      date_obs_orig = None
    #~~~~~~~~~~~~~~~~~~~DATE AND TIME EDITED (UT)~~~~~~~~~~~~~~~~~~~~~~#AttributeError, AttributeError("'list' object has no attribute 'strip'")

    time_format = ""

    if obs_times!=None and date_obs_orig!=None:
      dates_0 = date_obs_orig[0].replace(" ","").split(".") #we need only the first date
      # for i in range(0,len(dates_0)): #because somewhate there are occure spaces (?)
      #   dates_0 = dates_0.replace(" ","")
      # print("dates_0 ",dates_0)
      try:
        obs_time = api.dmsToDeg(obs_times[0], ":")%24  #we need only first data just for time type checking
      except AttributeError:
        print("AttributeError 1", obs_times)
      #%24 because somewhere we have time like 24:05:30
      if obs_times[0].split(":")[0] == "24":
        time_split = obs_times[0].split(":")
        obs_times[0] = "00:"+time_split[1]+":"+time_split[2]
      if obs_time > 12 and  obs_time < 24:
        obs_date_tf = Time(f"{dates_0[-1]}-{dates_0[1]}-{dates_0[0]} {obs_times[0]}")
      else:
        obs_date_tf = Time(f"{dates_0[-1]}-{dates_0[1]}-{dates_0[0]} {obs_times[0]}")  + 1*u.day
        #+1 day because we have the first date of observations, but they were done after midnight
      # print("date ",obs_date_tf)

      date_sun = Time(f"{dates_0[-1]}-{dates_0[1]}-{dates_0[0]} 00:00:01") + 1*u.day #+1 day because we have the first date of observations, but we
      #need midnight, so there should be next date from given. We need the date_sun to calculate sunset and sunrise
      # print("date_sun ",date_sun)
      sunset, sunrise = sun_set_rise_time(date_sun,observatory)

      if obs_date_tf > sunset and obs_date_tf < sunrise: #check as if it is LT
        obs_sidt = obs_date_tf.sidereal_time("apparent",observatory.location.lon).value+6

        if ra_edit[0]==ra_edit[0] and ra_edit[0]!=None:
          #hh:mm:ss to float
          ra_float = api.dmsToDeg(ra_edit[0], ":") #we pretend we have degrees because conversation hh:mm:ss to XX.XX
          delta = abs(ra_float - obs_time)
          dec_float = api.dmsToDeg(dec_edit[0], ":")
          phi = observatory.location.lat.value
          hour_angle = obs_sidt - ra_float
          altitude = get_object_altitude(dec_float,phi,hour_angle)

          if altitude > 10:
            time_format = "LT "
            date_obs_edit = convert_local_date_time_UT(date_obs_orig, obs_times) #UT

          else:#too low, so we suppose ST is given
            ra_float = api.dmsToDeg(ra_edit[0], ":") #we pretend we have degrees because conversation hh:mm:ss to XX.XX
            delta = abs(ra_float - obs_time)
            dec_float = api.dmsToDeg(dec_edit[0], ":")
            phi = observatory.location.lat.value
            hour_angle = obs_time - ra_float # we pretend that obs_time is ST
            altitude = get_object_altitude(dec_float,phi,hour_angle)

            if altitude > 10:
              time_format = "LST "
              obs_lt = get_lt_from_st(date_obs_orig, obs_times)
              date_obs_edit = obs_lt - get_delta_real(obs_lt)
            else:
              time_format = "Neither LT nor ST"########################################################################
              date_obs_edit = None
              counter =+ 1
        else:
          time_format = "LT " #because observational time at night and we will believe that the time is okay for object too
          date_obs_edit = convert_local_date_time_UT(date_obs_orig, obs_times) #UT

      else:#it is not LT because time is not at night, so probably it is ST
        if ra_edit[0]==ra_edit[0] and ra_edit[0]!=None:
          #hh:mm:ss to float
          # print(i,ra_edit[0])
          ra_float = api.dmsToDeg(ra_edit[0], ":") #we pretend we have degrees because conversation hh:mm:ss to XX.XX
          delta = abs(ra_float - obs_time)
          dec_float = api.dmsToDeg(dec_edit[0], ":")
          phi = observatory.location.lat.value
          hour_angle = obs_time - ra_float # we suppose that obs_time is ST
          altitude = get_object_altitude(dec_float,phi,hour_angle)

          if altitude > 10:
            time_format = "LST "
            obs_lt = get_lt_from_st(date_obs_orig, obs_times)[0]
            date_obs_edit = obs_lt - get_delta_real(obs_lt)

          else:
            time_format = "Neither LT nor ST"  ########################################################################
            date_obs_edit = None
            counter =+ 1

        else:
          time_format = "LST "
          obs_lt = get_lt_from_st(date_obs_orig, obs_times)[0]
          date_obs_edit = obs_lt - get_delta_real(obs_lt)

    elif obs_times!=None and date_obs_orig!=None and date_obs_orig==None:
      time_format = ""

    elif obs_times==None and date_obs_orig!=None and date_obs_orig!=None:
      if ra_edit[0]:
        try:
          obs_st = api.dmsToDeg(ra_edit[0], ":") #we pretend we have degrees because conversation hh:mm:ss to XX.XX
        except AttributeError:
          print("AttributeError 2", ra_edit)
        delta_st = get_sid_delta(date_obs_orig, [obs_st])[0]
        dates_0 = date_obs_orig[0].replace(" ","").split(".") #we need only the first date
        date_sun = Time(f"{dates_0[-1]}-{dates_0[1]}-{dates_0[0]} 00:00:01") + 1*u.day #+1 day because we have the first date of observations, but we
        obs_lt = date_sun + delta_st*u.hour
        date_obs_edit = obs_lt - get_delta_real(obs_lt)
        time_format = "Time from RA "
      else:
        dates_0 = date_obs_orig[0].replace(" ","").split(".") #we need only the first date
        date_mid = Time(f"{dates_0[-1]}-{dates_0[1]}-{dates_0[0]} 00:00:01") + 1*u.day
        date_obs_edit = date_mid - get_delta_real(date_mid)
        time_format = "Midnight "

    else: #we have nothing
      date_obs_edit = None
    

    #~~~~~~~~~~~~~~~~~~~TRANSLITERATION ~~~~~~~~~~~~~~~~~~~~~~
    try:
      observer_edit = translit(observer, 'ru', reversed=True)
    except AttributeError:
      observer_edit = None
    try:
      emulsion_edit = translit(emulsion, 'ru', reversed=True) #cause there some ru names
    except AttributeError:
      emulsion_edit = None

    #~~~~~~~~~~~~~~~~~~~DICTIONARY ~~~~~~~~~~~~~~~~~~~~~~
    if telescope:
      telescope_edit = TELESCOPE_ENG[telescope.lower().replace(" ","")] #####################MAY BE WE SHOULD USE UPPER CASE TO COMPAIR VALUE WITH DICTIONARY
    else:
      telescope_edit = None

    if telescope_edit:
      foclen = TELESCOPE_PARAM_DIC.get(telescope_edit)[0]
      field = TELESCOPE_PARAM_DIC.get(telescope_edit)[2]
      mirror_diameter =  TELESCOPE_PARAM_DIC.get(telescope_edit)[-1]
    else:
      foclen = None
      field = None
      mirror_diameter = None

    if size:
      plate_size = size.split("*")
    else:
      plate_size = TELESCOPE_PARAM_DIC.get(telescope)
      
      if plate_size:
        plate_size = plate_size[1]

    if method:
      method_edit = METHOD_ENG[method.lower().replace(" ","")]
    else:
      method_edit = None

    if filters:
      #Remove spaces, dots; replace commas and pluses with semicolon; use lower case
      filters_edit = [FILTERS_ENG["".join(filt.split()).lower()] for filt in filters.replace(" ","").replace(".","").replace(",",";").replace("+",";").split(";")]
    else:
      filters_edit = None

    if exptime:
      numexp=len(parse_exposure_times(exptime))
      variable_arguments = get_exposure_cards(exptime)
    else:
      numexp = None
      variable_arguments = {"EXPTIME": None} 
    #~~~~~~~~~~~~~~~HEADER WITH EDITED DATA~~~~~~~~~~~~~~~~~~

    if date_obs:
      variable_arguments.update(get_date_cards(date_obs))

    if objtype:
      variable_arguments.update(get_objtype_cards(objtype))
      
    if obj_name:
      object_name = obj_name.split(";")[0]
    else:
      object_name = None
    #  variable_arguments.update(get_object_cards(obj_name))

    if tms_lst:
      variable_arguments.update(get_time_start_cards(tms_lst, time_format))
    elif tms_lt:
      variable_arguments.update(get_time_start_cards(tms_lt, time_format))
    else:
      variable_arguments.update({"TMS-ORIG":None})

    if tme_lst:
      variable_arguments.update(get_time_end_cards(tme_lst, time_format))
    elif tme_lt:
      variable_arguments.update(get_time_end_cards(tme_lt, time_format))
    else:
      variable_arguments.update({"TME-ORIG":None})

    if filters_edit:
      variable_arguments.update(get_filters_cards(filters_edit))

   # for to_delete in ["IRAF-MAX", "IRAF-MIN", "IRAF-BPX"]:
   #   del hdr[to_delete]
    if not ra_edit:
      ra_edit = [None]
    if not dec_edit:
      dec_edit=[None]
    if not plate_size:
      plate_size = [None, None]
    if date_obs_edit:
      if type(date_obs_edit)==list:
        date_obs_edit=date_obs_edit[0]
      else:
        date_obs_edit=date_obs_edit.fits


    new_hdr = fitstricks.makeHeaderFromTemplate(
      fitstricks.WFPDB_TEMPLATE,
      originalHeader = hdr,
      OBJECT = object_name,
      DATE_OBS = date_obs_edit,
      RA_ORIG = ra_edit[0],
      DEC_ORIG = dec_edit[0],
      RA_DEG = ra_deg,
      DEC_DEG = dec_deg,
      OBSERVER = observer_edit,
      OBSERVAT = "Fesenkov Astrophysical Institute",
      SITELONG = 43.17667,
      SITELAT = 76.96611,
      SITEELEV = 1450,
      TELESCOP = telescope_edit,
      NUMEXP = numexp,
      SCANAUTH = "Shomshekova S., Umirbayeva A., Moshkina S.",
      ORIGIN = "Contant",
      FOCLEN = foclen,
      FOCUS = focus,
      METHOD = method_edit,
      PLATESZ1 = plate_size[0],
      PLATESZ2 = plate_size[1],
      FIELD = field,
      OTA_DIAM = mirror_diameter,
      SCANERS1 = 1200,
      SCANERS2 = 1200,
      PRE_PROC = "Cleaning from dust with a squirrel brush and from contamination from the glass (not an emulsion) with paper napkins",
      PID = plate_id,
      NOTES = notes,
      PLATNOTE = platenotes,
      SCANNOTE = scannotes,
      OBSNOTE = obsnotes,
      EMULSION = emulsion_edit,
      DETNAME = "Photographic plate",
      SKYCOND = skycond,
      FILENAME = self.fits_name.replace('.fit',''),
      **variable_arguments)

    self.fits_file[0].header = new_hdr
    self.fits_file.writeto("/var/gavo/inputs/schmidt_telescope_lc/data_astrometry_test/"+self.fits_name, output_verify="fix",overwrite=True) 
    return new_hdr

if __name__=="__main__":
  api.procmain(PAHeaderAdder, "schmidt_telescope_lc/q", "import")
