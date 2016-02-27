#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CommandLine:
    python -m ibeis.scripts.rsync_ibeisdb
    python -m ibeis.scripts.rsync_ibeisdb --dryrun
"""
from __future__ import absolute_import, division, print_function
import utool as ut


def sync_ibeisdb(remote_uri, dbname, mode='pull', workdir=None, port=22, dryrun=False):
    """
    syncs an ibeisdb without syncing the cache or the chip directory
    (or the top level image directory because it shouldnt exist unless it is an
    old hots database)
    """
    print('[sync_ibeisdb] Syncing')
    print('  * dbname=%r ' % (dbname,))
    print('  * remote_uri=%r' % (remote_uri,))
    print('  * mode=%r' % (mode))
    import ibeis
    # Excluded temporary and cached data
    exclude_dirs = list(map(ut.ensure_unixslash, ibeis.const.EXCLUDE_COPY_REL_DIRS))
    # Specify local workdir
    if workdir is None:
        workdir = ibeis.sysres.get_workdir()
    local_uri = ut.ensure_unixslash(workdir)
    if ut.WIN32:
        # fix for mingw rsync
        local_uri = ut.ensure_mingw_drive(local_uri)
    if mode == 'pull':
        # pull remote to local
        remote_src = ut.unixjoin(remote_uri, dbname)
        ut.assert_exists(local_uri)
        ut.rsync(remote_src, local_uri, exclude_dirs, port, dryrun=dryrun)
    elif mode == 'push':
        # push local to remote
        local_src = ut.unixjoin(local_uri, dbname)
        if not dryrun:
            ut.assert_exists(local_src)
        ut.rsync(local_src, remote_uri, exclude_dirs, port, dryrun=dryrun)
        if dryrun:
            ut.assert_exists(local_src)
    else:
        raise AssertionError('unknown mode=%r' % (mode,))


def rsync_ibsdb_main():
    import sys
    default_user = ut.get_user_name()
    default_db = 'MUGU_Master'
    if len(sys.argv) < 2:
        print('Usage: '
              'python -m ibeis.scripts.rsync_ibeisdb'
              '[push, pull] --db <db=%s> --user <user=%s>' %
              (default_db, default_user,))
        sys.exit(1)
    user = ut.get_argval('--user', type_=str, default=default_user)
    port = ut.get_argval('--port', type_=int, default=22)
    dbname = ut.get_argval(('--db', '--dbname'), type_=str, default=default_db)
    workdir = ut.get_argval(('--workdir', '--dbname'), type_=str, default=None,
                            help_='local work dir override')
    dry_run = ut.get_argflag(('--dryrun', '--dry-run', '--dry'))
    mode = sys.argv[1]

    assert mode in ['push', 'pull'], 'mode=%r must be push or pull' % (mode,)
    remote_key = ut.get_argval('--remote', type_=str, default='hyrule')
    remote_map = {
        'hyrule': 'hyrule.cs.rpi.edu',
        'pachy': 'pachy.cs.uic.edu',
        'lewa': '41.203.223.178',
        'lev': 'lev.cs.rpi.edu',
    }
    remote_workdir_map = {
        'hyrule': '/raid/work',
        'pachy': '/home/shared_ibeis/data/work',
        'lewa': '/data/ibeis',
        'lev': '/media/hdd/work',
    }
    if ':' in remote_key:
        remote_key_, remote_workdir = remote_key.split(':')
    else:
        remote_key_ = remote_key
        remote_workdir = remote_workdir_map.get(remote_key, '')

    remote = remote_map.get(remote_key_, remote_key_)
    remote_uri = user + '@' + remote + ':' + remote_workdir

    ut.change_term_title('RSYNC IBEISDB %r' % (dbname,))
    sync_ibeisdb(remote_uri, dbname, mode, workdir, port, dry_run)


if __name__ == '__main__':
    """
    CommandLine:
        ib
        python -m ibeis.scripts.rsync_ibeisdb push
        python -m ibeis.scripts.rsync_ibeisdb pull --db MUGU_Master
        python -m ibeis.scripts.rsync_ibeisdb pull --db GIRM_MUGU_20
        python -m ibeis.scripts.rsync_ibeisdb pull --db PZ_MUGU_ALL
        python -m ibeis.scripts.rsync_ibeisdb push --db MUGU_Master  --user joncrall --dryrun

        mv "NNP_Master3_nids=arr((3)wjybfvpk)_1" NNP_Master3_nids=arr__3_wjybfvpk__1

        python -m ibeis.scripts.rsync_ibeisdb pull --db NNP_Master3_nids=arr__3_wjybfvpk__1 --user jonc  --remote pachy --dryrun
        python -m ibeis.scripts.rsync_ibeisdb pull --db NNP_Master3_nids=arr__3_wjybfvpk__1 --user jonc  --remote pachy
        python -m ibeis.scripts.rsync_ibeisdb pull --db NNP_Master3 --user jonc --remote pachy
        python -m ibeis.scripts.rsync_ibeisdb pull --db testdb3 --user joncrall --remote hyrule
        python -m ibeis.scripts.rsync_ibeisdb pull --db NNP_MasterGIRM_core --user jonc --remote pachy

        #python -m ibeis.scripts.rsync_ibeisdb push --db lewa_grevys --user joncrall --remote hyrule --port 1022 --workdir=/data/ibeis --dryrun
        python -m ibeis.scripts.rsync_ibeisdb pull --db lewa_grevys --user jonathan --remote lewa --port 1022 --dryrun

        python -m ibeis.scripts.rsync_ibeisdb push --db ELEPH_Master --user jonc --remote pachy --workdir=/raid/work2/Turk --dryrun
        python -m ibeis.scripts.rsync_ibeisdb push --db ELPH_Master --user jonc --remote pachy --workdir=/raid/work2/Turk

        python -m ibeis.scripts.rsync_ibeisdb pull --db PZ_ViewPoints --user joncrall --remote hyrule --dryrun

        python -m ibeis.scripts.rsync_ibeisdb push --db PZ_Master1 --user joncrall --remote lev --dryrun


        stty -echo; ssh jonc@pachy.cs.uic.edu sudo -v; stty echo
        rsync -avhzP -e "ssh -p 22" --rsync-path="sudo rsync" jonc@pachy.cs.uic.edu:/home/ibeis-repos/snow-leopards /raid/raw_rsync
        rsync -avhzP -e "ssh -p 22" jonc@pachy.cs.uic.edu:snow-leopards /raid/raw_rsync
        rsync -avhzP -e "ssh -p 22" jonc@pachy.cs.uic.edu:iberian-lynx /raid/raw_rsync
        rsync -avhzP -e "ssh -p 22" --rsync-path="sudo rsync" jonc@pachy.cs.uic.edu:/home/ibeis-repos/african-dogs /raid/raw_rsync

        # make sure group read bits are set
        ssh -t jonc@pachy.cs.uic.edu "sudo chown -R apache:ibeis /home/ibeis-repos/"
        ssh -t jonc@pachy.cs.uic.edu "sudo chmod -R g+r /home/ibeis-repos"
        rsync -avhzP -e "ssh -p 22" jonc@pachy.cs.uic.edu:/home/ibeis-repos/african-dogs /raid/raw_rsync
        rsync -avhzP -e "ssh -p 22" joncrall@hyrule.cs.rpi.edu/raid/raw_rsync/iberian-lynx .
        rsync -avhzP joncrall@hyrule.cs.rpi.edu:/raid/raw_rsync/iberian-lynx .

        python -m ibeis.scripts.rsync_ibeisdb pull --db humpbacks --user joncrall --remote lev:/home/zach/data/IBEIS/ --dryrun
        python -m ibeis.scripts.rsync_ibeisdb pull --db humpbacks --user joncrall --remote lev:/home/zach/data/IBEIS/

        python -m ibeis.scripts.rsync_ibeisdb pull --db humpbacks_fb --user joncrall --remote lev:/home/zach/data/IBEIS/

        /home/zach/data/IBEIS/humpbacks_fb

        python -m ibeis.scripts.rsync_ibeisdb pull --db seaturtles2 --user 'ubuntu' --remote drewami:/data/ibeis

    Fix Patchy
        pachy
        cd /home/ibeis-repos
        sudo chmod -R g+r *


    Feasibility Testing Example:

        # --- GET DATA ---
        ssh -t jonc@pachy.cs.uic.edu "sudo chmod -R g+r /home/ibeis-repos"
        rsync -avhzP jonc@pachy.cs.uic.edu:/home/ibeis-repos/african-dogs /raid/raw_rsync
        rsync -avhzP drewami:turtles .


    WildDog Example:

        # --- GET DATA ---
        # make sure group read bits are set
        ssh -t jonc@pachy.cs.uic.edu "sudo chown -R apache:ibeis /home/ibeis-repos/"
        ssh -t jonc@pachy.cs.uic.edu "sudo chmod -R g+r /home/ibeis-repos"
        rsync -avhzP jonc@pachy.cs.uic.edu:/home/ibeis-repos/african-dogs /raid/raw_rsync

        # --- GET DATA ---
        # Get the data via rsync, pydio. (I always have issues doing this with
        # rsync on pachy, so I usually just do it manually)

        rsync -avhzP <user>@<host>:<remotedir>  <path-to-raw-imgs>

        # --- RUN INGEST SCRIPT ---
        # May have to massage folder names things to make everything work. Can
        # also specify fmtkey to use the python parse module to find the name
        # within the folder names.
        python -m ibeis --tf ingest_rawdata --db <new-ibeis-db-name> --imgdir <path-to-raw-imgs> --ingest-type=named_folders --species=<optional> --fmtkey=<optional>

        # --- OPEN DATABASE / FIX PROBLEMS ---
        ibeis --db <new-ibeis-db-name>

        # You will probably need to fix some bounding boxes.

        # --- LAUNCH IPYTHON NOTEBOOK ---
        # Then click Dev -> Launch IPython Notebook and run it
        # OR RUN
        ibeis --tf autogen_ipynb --db <new-ibeis-db-name> --ipynb


        Here is what I did for wild dogs
        # --- GET DATA ---
        # Download raw data to /raid/raw_rsync/african-dogs
        rsync -avhzP jonc@pachy.cs.uic.edu:/home/ibeis-repos/african-dogs /raid/raw_rsync

        # --- RUN INGEST SCRIPT ---
        python -m ibeis --tf ingest_rawdata --db wd_peter2 --imgdir /raid/raw_rsync/african-dogs --ingest-type=named_folders --species=wild_dog --fmtkey='African Wild Dog: {name}'

        # --- OPEN DATABASE / FIX PROBLEMS ---
        ibeis --db wd_peter2
        # Fixed some bounding boxes

        # --- LAUNCH IPYTHON NOTEBOOK ---
        # I actually made two notebooks for this species to account for timedeltas

        # The first is the default notebook
        ibeis --tf autogen_ipynb --db wd_peter --ipynb

        # The second removes images without timestamps and annotations that are too close together in time
        ibeis --tf autogen_ipynb --db wd_peter --ipynb -t default:is_known=True,min_timedelta=3600,require_timestamp=True,min_pername=2

        # I then click download as html in the notebook. Although I'm sure there is a way to automate this

    """
    rsync_ibsdb_main()
