"""
short term archiving
"""

import shutil, glob, re, os

from CIME.XML.standard_module_setup import *
from CIME.case_submit               import submit
from CIME.XML.env_archive           import EnvArchive
from CIME.utils                     import run_and_log_case_status
from os.path                        import isdir, join
import datetime

logger = logging.getLogger(__name__)

###############################################################################
def _get_file_date(filename):
###############################################################################
    """
    Returns the date associated with the filename as a datetime object representing the correct date
    Formats supported:
    "%Y-%m-%d_%h.%M.%s
    "%Y-%m-%d_%05s"
    "%Y-%m-%d-%05s"
    "%Y-%m-%d"
    "%Y-%m"
    "%Y.%m"

    >>> _get_file_date("./ne4np4_oQU240.cam.r.0001-01-06-00435.nc")
    datetime.datetime(1, 1, 6, 0, 7, 15)
    >>> _get_file_date("./ne4np4_oQU240.cam.r.0010-1-06_00435.nc")
    datetime.datetime(10, 1, 6, 0, 7, 15)
    >>> _get_file_date("./ne4np4_oQU240.cam.r.0010-10.nc")
    datetime.datetime(10, 10, 1, 0, 0)
    >>> _get_file_date("0064-3-8_10.20.30.nc")
    datetime.datetime(64, 3, 8, 10, 20, 30)
    >>> _get_file_date("0140-3-5")
    datetime.datetime(140, 3, 5, 0, 0)
    >>> _get_file_date("0140-3")
    datetime.datetime(140, 3, 1, 0, 0)
    >>> _get_file_date("0140.3")
    datetime.datetime(140, 3, 1, 0, 0)
    """

    #
    # TODO: Add these to config_archive.xml, instead of here
    # Note these must be in order of most specific to least
    # so that lesser specificities aren't used to parse greater ones
    re_formats = ["[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}_[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}", # yyyy-mm-dd_hh.MM.ss
                  "[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[\-_][0-9]{1,5}",                     # yyyy-mm-dd_sssss
                  "[0-9]{4}-[0-9]{1,2}-[0-9]{1,2}",                                    # yyyy-mm-dd
                  "[0-9]{4}[\-\.][0-9]{1,2}",                                          # yyyy-mm
    ]

    for re_str in re_formats:
        match = re.search(re_str, filename)
        if match is None:
            continue
        date_str = match.group()
        date_tuple = [int(unit) for unit in re.split("-|_|\.", date_str)]
        year = date_tuple[0]
        month = date_tuple[1]
        day = 1
        second = 0
        if len(date_tuple) > 2:
            day = date_tuple[2]
            if len(date_tuple) == 4:
                second = date_tuple[3]
            elif len(date_tuple) == 6:
                # Create a datetime object with arbitrary year, month, day, but the correct time of day
                # Then use _get_day_second to get the time of day in seconds
                second = _get_day_second(datetime.datetime(1, 1, 1,
                                                           hour = date_tuple[3],
                                                           minute = date_tuple[4],
                                                           second = date_tuple[5]))
        return datetime.datetime(year, month, day) + datetime.timedelta(seconds = second)

    # Not a valid filename date format
    raise ValueError("{} is a filename without a supported date!".format(filename))

def _get_day_second(date):
    """
    Returns the total seconds that have elapsed since the beginning of the day
    """
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_MINUTE = 60
    return (date.second
            + date.minute * SECONDS_PER_MINUTE
            + date.hour * SECONDS_PER_HOUR)

def _datetime_str(date):
    """
    Returns the standard format associated with filenames.
    Note unfortunately datetime.datetime.strftime expects years > 1900
    to support abbreviations, so we can't use that here

    >>> _datetime_str(datetime.datetime(5, 8, 22))
    '0005-08-22-00000'
    >>> _datetime_str(_get_file_date("0011-12-09-00435"))
    '0011-12-09-00435'
    """

    format_string = "{year:04d}-{month:02d}-{day:02d}-{seconds:05d}"
    return format_string.format(year = date.year,
                                month = date.month,
                                day = date.day,
                                seconds = _get_day_second(date))

def _datetime_str_mpas(date):
    """
    Returns the mpas format associated with filenames.
    Note unfortunately datetime.datetime.strftime expects years > 1900
    to support abbreviations, so we can't use that here

    >>> _datetime_str_mpas(datetime.datetime(5, 8, 22))
    '0005-08-22_00000'
    >>> _datetime_str_mpas(_get_file_date("0011-12-09-00435"))
    '0011-12-09_00435'
    """

    format_string = "{year:04d}-{month:02d}-{day:02d}_{seconds:05d}"
    return format_string.format(year = date.year,
                                month = date.month,
                                day = date.day,
                                seconds = _get_day_second(date))

###############################################################################
def _get_datenames(rundir, casename):
###############################################################################
    """
    Returns the datetime objects specifying the times of each file
    Note we are assuming that the coupler restart files exist and are consistent with other component datenames
    Not doc-testable due to filesystem dependence
    """
    logger.debug('In get_datename...')
    expect(isdir(rundir), 'Cannot open directory %s ' % rundir)
    files = sorted(glob.glob(os.path.join(rundir, casename + '.cpl.r*.nc')))
    if not files:
        expect(False, 'Cannot find a %s.cpl.r.*.nc file in directory %s ' % (casename, rundir))
    datenames = []
    for filename in files:
        date = _get_file_date(filename)
        datenames.append(date)
    return datenames

###############################################################################
def _get_ninst_info(case, compclass):
###############################################################################
    """
    Returns the number of instances used by a component and suffix strings for filenames
    Not doc-testable due to case dependence
    """

    if compclass != 'cpl':
        ninst = case.get_value('NINST_' + compclass.upper())
    else:
        ninst = 1
    ninst_strings = []
    if ninst is None:
        ninst = 1
    for i in range(1,ninst+1):
        if ninst > 1:
            ninst_strings.append('_' + '%04d' % i)
        else:
            ninst_strings.append('')

    logger.debug("ninst and ninst_strings are: %s and %s for %s" %(ninst, ninst_strings, compclass))
    return ninst, ninst_strings

###############################################################################
def _archive_rpointer_files(casename, ninst_strings, rundir, save_interim_restart_files, archive,
                            archive_entry, archive_restdir, datename, datename_is_last):
###############################################################################

    # archive the rpointer files associated with datename
    compclass = archive.get_entry_info(archive_entry)[1]

    if datename_is_last:
        # Copy of all rpointer files for latest restart date
        rpointers = glob.glob(os.path.join(rundir, 'rpointer.*'))
        for rpointer in rpointers:
            shutil.copy(rpointer, os.path.join(archive_restdir, os.path.basename(rpointer)))
    else:
        # Generate rpointer file(s) for interim restarts for the one datename and each
        # possible value of ninst_strings
        if save_interim_restart_files:

            # parse env_archive.xml to determine the rpointer files
            # and contents for the given archive_entry tag
            rpointer_items = archive.get_rpointer_contents(archive_entry)

            # loop through the possible rpointer files and contents
            for rpointer_file, rpointer_content in rpointer_items:
                # put in a temporary setting for ninst_strings if they are empty
                # in order to have just one loop over ninst_strings below
                if rpointer_content is not 'unset':
                    if not ninst_strings:
                        ninst_strings = ["empty"]
                for ninst_string in ninst_strings:
                    if ninst_string == 'empty':
                        ninst_string = ""
                    for key, value in [('$CASE', casename),
                                       ('$DATENAME', _datetime_str(datename)),
                                       ('$MPAS_DATENAME', _datetime_str_mpas(datename)),
                                       ('$NINST_STRING', ninst_string)]:
                        rpointer_file = rpointer_file.replace(key, value)
                        rpointer_content = rpointer_content.replace(key, value)

                    # write out the respect files with the correct contents
                    rpointer_file = os.path.join(archive_restdir, rpointer_file)
                    logger.info("writing rpointer_file %s" % rpointer_file)
                    f = open(rpointer_file, 'w')
                    for output in rpointer_content.split(','):
                        f.write("%s \n" %output)
                    f.close()

###############################################################################
def _archive_log_files(dout_s_root, rundir, archive_incomplete, archive_file_fn):
###############################################################################
    """
    Find all completed log files, or all log files if archive_incomplete is True, and archive them.
    Each log file is required to have ".log." in its name, and completed ones will end with ".gz"
    Not doc-testable due to file system dependence
    """
    archive_logdir = os.path.join(dout_s_root, 'logs')
    if not os.path.exists(archive_logdir):
        os.makedirs(archive_logdir)
        logger.debug("created directory %s " %archive_logdir)

    if archive_incomplete == False:
        log_search = '*.log.*.gz'
    else:
        log_search = '*.log.*'

    logfiles = glob.glob(os.path.join(rundir, log_search))
    for logfile in logfiles:
        srcfile = join(rundir, os.path.basename(logfile))
        destfile = join(archive_logdir, os.path.basename(logfile))
        archive_file_fn(srcfile, destfile)
        logger.info("moving %s to %s" %(srcfile, destfile))

###############################################################################
def _archive_history_files(case, archive, archive_entry,
                           compclass, compname, histfiles_savein_rundir,
                           last_date, archive_file_fn):
###############################################################################
    """
    perform short term archiving on history files in rundir
    
    Not doc-testable due to case and file system dependence
    """

    # determine history archive directory (create if it does not exist)
    dout_s_root = case.get_value("DOUT_S_ROOT")
    casename = case.get_value("CASE")
    archive_histdir = os.path.join(dout_s_root, compclass, 'hist')
    if not os.path.exists(archive_histdir):
        os.makedirs(archive_histdir)
        logger.debug("created directory %s" %archive_histdir)

    # determine ninst and ninst_string
    ninst, ninst_string = _get_ninst_info(case, compclass)

    # archive history files - the only history files that kept in the
    # run directory are those that are needed for restarts
    rundir = case.get_value("RUNDIR")
    for suffix in archive.get_hist_file_extensions(archive_entry):
        for i in range(ninst):
            if compname == 'dart':
                newsuffix = casename + suffix
            elif compname.find('mpas') == 0:
                newsuffix = compname + '.*' + suffix
            else:
                if ninst_string:
                    newsuffix = casename + '.' + compname + ".*" + ninst_string[i] + suffix
                else:
                    newsuffix = casename + '.' + compname + ".*" + suffix
            pfile = re.compile(newsuffix)
            histfiles = [f for f in os.listdir(rundir) if pfile.search(f)]
            if histfiles:
                for histfile in histfiles:
                    file_date = _get_file_date(os.path.basename(histfile))
                    if last_date is None or file_date <= last_date:
                        srcfile = join(rundir, histfile)
                        expect(os.path.isfile(srcfile),
                               "history file %s does not exist " %srcfile)
                        destfile = join(archive_histdir, histfile)
                        if histfile in histfiles_savein_rundir:
                            logger.info("copying \n%s to \n%s " %(srcfile, destfile))
                            shutil.copy(srcfile, destfile)
                        else:
                            logger.info("moving \n%s to \n%s " %(srcfile, destfile))
                            archive_file_fn(srcfile, destfile)

###############################################################################
def get_histfiles_for_restarts(rundir, archive, archive_entry, restfile):
###############################################################################
    """
    determine history files that are needed for restarts

    Not doc-testable due to filesystem dependence
    """

    # Make certain histfiles is a set so we don't repeat
    histfiles = set()
    rest_hist_varname = archive.get_entry_value('rest_history_varname', archive_entry)
    if rest_hist_varname != 'unset':
        cmd = "ncdump -v %s %s " %(rest_hist_varname, os.path.join(rundir, restfile))
        rc, out, error = run_cmd(cmd)
        if rc != 0:
            logger.debug(" WARNING: %s failed rc=%d\nout=%s\nerr=%s" %(cmd, rc, out, error))

        searchname = "%s =" %rest_hist_varname
        if searchname in out:
            offset = out.index(searchname)
            items = out[offset:].split(",")
            for item in items:
                # the following match has an option of having a './' at the beginning of
                # the history filename
                matchobj = re.search(r"\"(\.*\/*\w.*)\s?\"", item)
                if matchobj:
                    histfile = matchobj.group(1).strip()
                    histfile = os.path.basename(histfile)
                    # append histfile to the list ONLY if it exists in rundir before the archiving
                    if histfile in histfiles:
                        logger.info("WARNING, tried to add a duplicate file to histfiles")
                    if os.path.isfile(os.path.join(rundir,histfile)):
                        histfiles.add(histfile)
    return histfiles

###############################################################################
def _archive_restarts(case, archive, archive_entry,
                      compclass, compname, datename, datename_is_last,
                      last_date, archive_file_fn):
###############################################################################
    """
    First archives the rpointer files
    Next finds the restart files
    Then determines if they should be archived
    If so, get the histfiles for the restart
    If this is the last date, only copy files, otherwise move them for archiving
    """

    # determine directory for archiving restarts based on datename
    dout_s_root = case.get_value("DOUT_S_ROOT")
    rundir = case.get_value("RUNDIR")
    casename = case.get_value("CASE")
    datename_str = _datetime_str(datename)

    archive_restdir = join(dout_s_root, 'rest', datename_str)
    if not os.path.exists(archive_restdir):
        os.makedirs(archive_restdir)

    # archive the rpointer file(s) for this datename and all possible ninst_strings
    _archive_rpointer_files(casename, _get_ninst_info(case, compclass)[1], rundir,
                            case.get_value('DOUT_S_SAVE_INTERIM_RESTART_FILES'),
                            archive, archive_entry, archive_restdir, datename, datename_is_last)

    # determine ninst and ninst_string
    ninst, ninst_strings = _get_ninst_info(case, compclass)

    # move all but latest restart files into the archive restart directory
    # copy latest restart files to archive restart directory
    histfiles_savein_rundir = []

    # get file_extension suffixes
    for suffix in archive.get_rest_file_extensions(archive_entry):
        for i in range(ninst):
            restfiles = ""
            if compname.find("mpas") == 0:
                pattern = compname + suffix + '_'.join(datename_str.rsplit('-', 1))
                pfile = re.compile(pattern)
                restfiles = [f for f in os.listdir(rundir) if pfile.search(f)]
            else:
                pattern = r"%s\.%s\d*.*" % (casename, compname)
                if "dart" not in pattern:
                    pfile = re.compile(pattern)
                    files = [f for f in os.listdir(rundir) if pfile.search(f)]
                    if ninst_strings:
                        pattern = ninst_strings[i] + suffix + datename_str
                        pfile = re.compile(pattern)
                        restfiles = [f for f in files if pfile.search(f)]
                    else:
                        pattern = suffix + datename_str
                        pfile = re.compile(pattern)
                        restfiles = [f for f in files if pfile.search(f)]
                else:
                    pattern = suffix
                    pfile = re.compile(pattern)
                    restfiles = [f for f in os.listdir(rundir) if pfile.search(f)]

            for restfile in restfiles:
                restfile = os.path.basename(restfile)

                file_date = _get_file_date(restfile)
                if last_date is not None and file_date > last_date:
                    # Skip this file
                    continue

                if not os.path.exists(archive_restdir):
                    os.makedirs(archive_restdir)

                # obtain array of history files for restarts
                # need to do this before archiving restart files
                histfiles_for_restart = get_histfiles_for_restarts(rundir, archive,
                                                                   archive_entry, restfile)

                if datename_is_last and histfiles_for_restart:
                    for histfile in histfiles_for_restart:
                        if histfile not in histfiles_savein_rundir:
                            histfiles_savein_rundir.append(histfile)

                # archive restart files and all history files that are needed for restart
                # Note that the latest file should be copied and not moved
                if datename_is_last:
                    srcfile = os.path.join(rundir, restfile)
                    destfile = os.path.join(archive_restdir, restfile)
                    shutil.copy(srcfile, destfile)
                    logger.info("copying \n%s to \n%s" %(srcfile, destfile))

                    for histfile in histfiles_for_restart:
                        srcfile = os.path.join(rundir, histfile)
                        destfile = os.path.join(archive_restdir, histfile)
                        expect(os.path.isfile(srcfile),
                               "history restart file for last date %s does not exist " % srcfile)
                        shutil.copy(srcfile, destfile)
                        logger.info("copying \n%s to \n%s" %(srcfile, destfile))
                else:
                    # Only archive intermediate restarts if requested - otherwise remove them
                    if case.get_value('DOUT_S_SAVE_INTERIM_RESTART_FILES'):
                        srcfile = os.path.join(rundir, restfile)
                        destfile = os.path.join(archive_restdir, restfile)
                        logger.info("moving \n%s to \n%s" %(srcfile, destfile))
                        expect(os.path.isfile(srcfile),
                               "restart file %s does not exist " %srcfile)
                        archive_file_fn(srcfile, destfile)
                        logger.info("moving \n%s to \n%s" %(srcfile, destfile))

                        # need to copy the history files needed for interim restarts - since
                        # have not archived all of the history files yet
                        for histfile in histfiles_for_restart:
                            srcfile = os.path.join(rundir, histfile)
                            destfile = os.path.join(archive_restdir, histfile)
                            expect(os.path.isfile(srcfile),
                                   "hist file %s does not exist " %srcfile)
                            shutil.copy(srcfile, destfile)
                            logger.info("copying \n%s to \n%s" %(srcfile, destfile))
                    else:
                        srcfile = os.path.join(rundir, restfile)
                        logger.info("removing interim restart file %s" %srcfile)
                        if (os.path.isfile(srcfile)):
                            try:
                                os.remove(srcfile)
                            except OSError:
                                logger.warn("unable to remove interim restart file %s" %srcfile)
                        else:
                            logger.warn("interim restart file %s does not exist" %srcfile)

    return histfiles_savein_rundir

###############################################################################
def _archive_process(case, archive, last_date, archive_incomplete_logs, copy_only):
###############################################################################
    """
    Parse config_archive.xml and perform short term archiving
    """

    logger.debug('In archive_process...')
    compset_comps = case.get_compset_components()
    compset_comps.append('cpl')
    compset_comps.append('dart')

    if copy_only is True:
        archive_file_fn = shutil.copyfile
    else:
        archive_file_fn = shutil.move

    # archive log files
    _archive_log_files(case.get_value("DOUT_S_ROOT"), case.get_value("RUNDIR"),
                       archive_incomplete_logs, archive_file_fn)

    for archive_entry in archive.get_entries():
        # determine compname and compclass
        compname, compclass = archive.get_entry_info(archive_entry)

        # check for validity of compname
        if compname not in compset_comps:
            continue

        # archive restarts and all necessary associated fields (e.g. rpointer files)
        logger.info('-------------------------------------------')
        logger.info('doing short term archiving for %s (%s)' % (compname, compclass))
        logger.info('-------------------------------------------')
        datenames = _get_datenames(case.get_value('RUNDIR'), case.get_value('CASE'))
        for i, datename in enumerate(datenames):
            logger.info('Archiving for date %s' % datename)
            datename_is_last = False
            if i == len(datenames) - 1:
                datename_is_last = True

            # archive restarts
            histfiles_savein_rundir = _archive_restarts(case, archive, archive_entry,
                                                        compclass, compname,
                                                        datename, datename_is_last,
                                                        last_date, archive_file_fn)

            # if the last datename for restart files, then archive history files
            # for this compname
            if datename_is_last:
                logger.info("histfiles_savein_rundir %s " %histfiles_savein_rundir)
                _archive_history_files(case, archive, archive_entry,
                                       compclass, compname, histfiles_savein_rundir,
                                       last_date, archive_file_fn)

###############################################################################
def restore_from_archive(case):
###############################################################################
    """
    Take most recent archived restart files and load them into current case.
    """
    dout_sr = case.get_value("DOUT_S_ROOT")
    rundir = case.get_value("RUNDIR")
    most_recent_rest = run_cmd_no_fail("ls -1dt %s/rest/* | head -1" % dout_sr)

    for item in glob.glob("%s/*" % most_recent_rest):
        base = os.path.basename(item)
        dst = os.path.join(rundir, base)
        if os.path.exists(dst):
            os.remove(dst)

        shutil.copy(item, rundir)

###############################################################################
def case_st_archive(case, last_date_str=None, archive_incomplete_logs=True, copy_only=False, no_resubmit=False):
###############################################################################
    """
    Create archive object and perform short term archiving
    """
    caseroot = case.get_value("CASEROOT")

    if last_date_str is not None:
        try:
            last_date = datetime.datetime.strptime(last_date_str, '%Y-%m-%d')
        except ValueError:
            expect(False, 'Could not parse the last date to archive')
    else:
        last_date = None

    dout_s_root = case.get_value('DOUT_S_ROOT')
    if dout_s_root is None or dout_s_root == 'UNSET':
        expect(False,
               'XML variable DOUT_S_ROOT is required for short-term achiver')
    if not isdir(dout_s_root):
        os.makedirs(dout_s_root)

    dout_s_save_interim = case.get_value('DOUT_S_SAVE_INTERIM_RESTART_FILES')
    if dout_s_save_interim == 'FALSE' or dout_s_save_interim == 'UNSET':
        rest_n = case.get_value('REST_N')
        stop_n = case.get_value('STOP_N')
        if rest_n < stop_n:
            logger.warn('Restart files from end of run will be saved'
                        'interim restart files will be deleted')

    logger.info("st_archive starting")

    archive = EnvArchive(infile=os.path.join(caseroot, 'env_archive.xml'))
    functor = lambda: _archive_process(case, archive, last_date, archive_incomplete_logs, copy_only)
    run_and_log_case_status(functor, "st_archive", caseroot=caseroot)

    logger.info("st_archive completed")

    # resubmit case if appropriate
    resubmit = case.get_value("RESUBMIT")
    if resubmit > 0 and not no_resubmit:
        logger.info("resubmitting from st_archive, resubmit=%d"%resubmit)
        if case.get_value("MACH") == "mira":
            expect(os.path.isfile(".original_host"), "ERROR alcf host file not found")
            with open(".original_host", "r") as fd:
                sshhost = fd.read()
            run_cmd("ssh cooleylogin1 ssh %s '%s/case.submit %s --resubmit' "\
                        %(sshhost, caseroot, caseroot), verbose=True)
        else:
            submit(case, resubmit=True)

    return True
