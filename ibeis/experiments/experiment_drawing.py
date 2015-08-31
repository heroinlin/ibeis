# -*- coding: utf-8 -*-
"""
./dev.py -t custom:affine_invariance=False,adapteq=True,fg_on=False --db Elephants_drop1_ears --allgt --index=0:10 --guiview
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import numpy as np
#from ibeis import params
import utool as ut
from ibeis.experiments import experiment_storage
from ibeis.model.hots import match_chips4 as mc4
from os.path import join, dirname, split, basename, splitext
from plottool import draw_func2 as df2
#from plottool import plot_helpers as ph
from six.moves import map, range, input  # NOQA
print, print_, printDBG, rrr, profile = ut.inject(__name__, '[expt_drawres]')
SKIP_TO = ut.get_argval(('--skip-to', '--skipto'), type_=int, default=None)
#SAVE_FIGURES = ut.get_argflag(('--save-figures', '--sf'))
SAVE_FIGURES = not ut.get_argflag(('--nosave-figures', '--nosf'))

SHOW                 = ut.get_argflag('--show')

# only triggered if dump_extra is on
DUMP_PROBCHIP = False
DUMP_REGCHIP = False


#fontkw = dict(legendsize=8, labelsize=10, ticksize=8, titlesize=8)
FONTKW = dict(legendsize=12, labelsize=12, ticksize=12, titlesize=14)


def draw_rank_surface(ibs, test_result):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        test_result (?):

    CommandLine:
        python -m ibeis.dev -e draw_rank_surface --show  -t candidacy_k -a varysize  --db PZ_MTEST --show
        python -m ibeis.dev -e draw_rank_surface --show  -t candidacy_k -a varysize  --db PZ_Master0 --show
        python -m ibeis.dev -e draw_rank_surface --show  -t candidacy_k -a varysize2  --db PZ_Master0 --show

        python -m ibeis.dev -e draw_rank_surface -t candidacy_k -a varysize:qsize=500,dsize=[500,1000,1500,2000,2500,3000] --db PZ_Master1 --show


    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> from ibeis.init import main_helpers
        >>> ibs, test_result = main_helpers.testdata_expts('PZ_MTEST')
        >>> result = draw_rank_surface(ibs, test_result)
        >>> ut.show_if_requested()
        >>> print(result)
    """
    rank_le1_list = test_result.get_rank_cumhist(bins='dense')[0].T[0]
    percent_le1_list = 100 * rank_le1_list / len(test_result.qaids)
    #test_result.cfgx2_lbl
    #test_result.get_param_basis('dcfg_sample_per_name')
    #test_result.get_param_basis('dcfg_sample_size')
    #K_basis = test_result.get_param_basis('K')
    #K_cfgx_lists = [test_result.get_cfgx_with_param('K', K) for K in K_basis]

    #param_key_list = test_result.get_all_varied_params()
    param_key_list = ['K', 'dcfg_sample_per_name', 'dcfg_sample_size']
    #param_key_list = ['K', 'dcfg_sample_per_name', 'len(daids)']
    basis_dict      = {}
    cfgx_lists_dict = {}
    for key in param_key_list:
        _basis = test_result.get_param_basis(key)
        _cfgx_list = [test_result.get_cfgx_with_param(key, val) for val in _basis]
        cfgx_lists_dict[key] = _cfgx_list
        basis_dict[key] = _basis
    print('basis_dict = ' + ut.dict_str(basis_dict, nl=1, hack_liststr=True))
    print('cfx_lists_dict = ' + ut.dict_str(cfgx_lists_dict, nl=2, hack_liststr=True))

    # Hold a key constant
    import plottool as pt
    #const_key = 'K'
    const_key = 'dcfg_sample_per_name'
    #pnum_ = pt.make_pnum_nextgen(*pt.get_square_row_cols(len(basis_dict[const_key]), max_cols=1))
    pnum_ = pt.make_pnum_nextgen(*pt.get_square_row_cols(len(basis_dict[const_key])))
    #ymax = percent_le1_list.max()
    #ymin = percent_le1_list.min()
    # Use consistent markers and colors.
    color_list = pt.distinct_colors(len(basis_dict[param_key_list[-1]]))
    marker_list = pt.distinct_markers(len(basis_dict[param_key_list[-1]]))
    for const_idx, const_val in enumerate(basis_dict[const_key]):
        const_basis_cfgx_list = cfgx_lists_dict[const_key][const_idx]
        rank_list = ut.list_take(percent_le1_list, const_basis_cfgx_list)
        # Figure out what the values are for other dimensions
        agree_param_vals = dict([
            (key, [test_result.get_param_val_from_cfgx(cfgx, key) for cfgx in const_basis_cfgx_list])
            for key in param_key_list if key != const_key])

        from ibeis.experiments import annotation_configs
        nd_labels = list(agree_param_vals.keys())
        nd_labels = [annotation_configs.shorten_to_alias_labels(key) for key in nd_labels]
        target_label = annotation_configs.shorten_to_alias_labels(key)

        #target_label = 'num rank ≤ 1'
        #label_list = [ut.scalar_str(percent, precision=2) + '% - ' + label for percent, label in zip(cdf_list.T[0], label_list)]
        target_label = '% queries = rank 1'
        known_nd_data = np.array(list(agree_param_vals.values())).T
        known_target_points = np.array(rank_list)
        #title = ('% Ranks = 1 when ' + annotation_configs.shorten_to_alias_labels(const_key) + '=%r' % (const_val,))
        title = ('Accuracy when ' + annotation_configs.shorten_to_alias_labels(const_key) + '=%r' % (const_val,))
        #PLOT3D = not ut.get_argflag('--no3dsurf')
        PLOT3D = ut.get_argflag('--no2dsurf')
        if PLOT3D:
            pt.plot_search_surface(known_nd_data, known_target_points, nd_labels, target_label, title=title, fnum=1, pnum=pnum_())
        else:
            nonconst_basis_vals = np.unique(known_nd_data.T[1])
            # Find which colors will not be used
            nonconst_covers_basis = np.in1d(basis_dict[param_key_list[-1]], nonconst_basis_vals)
            nonconst_color_list = ut.list_compress(color_list, nonconst_covers_basis)
            nonconst_marker_list = ut.list_compress(marker_list, nonconst_covers_basis)
            pt.plot_multiple_scores(known_nd_data, known_target_points,
                                    nd_labels, target_label, title=title,
                                    color_list=nonconst_color_list,
                                    marker_list=nonconst_marker_list, fnum=1,
                                    pnum=pnum_(), num_yticks=8, ymin=30, ymax=100, ypad=.5,
                                    xpad=.05, legend_loc='lower right', **FONTKW)
            #pt.plot2(
        #(const_idx + 1))

    figtitle = (
        #'Effect of ' + ut.conj_phrase(nd_labels, 'and') + ' on #Ranks = 1 for\n')
        'Effect of ' + ut.conj_phrase(nd_labels, 'and') + ' on Accuracy for\n')
    figtitle += ' ' + test_result.get_title_aug()

    #if ut.get_argflag('--save'):
    # hack
    if ut.NOT_QUIET:
        test_result.print_unique_annot_config_stats()

    #if test_result.has_constant_daids():
    #    print('test_result.common_acfg = ' + ut.dict_str(test_result.common_acfg))
    #    annotconfig_stats_strs, locals_ = ibs.get_annotconfig_stats(test_result.qaids, test_result.cfgx2_daids[0])
    pt.set_figtitle(figtitle, size=14)


def draw_rank_cdf(ibs, test_result):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        test_result (?):

    CommandLine:

        python -m ibeis.dev -e draw_rank_cdf
        python -m ibeis.dev -e draw_rank_cdf --db PZ_MTEST --show
        python -m ibeis.dev -e draw_rank_cdf --db PZ_MTEST --show -a varysize -t default
        python -m ibeis.dev -e draw_rank_cdf --db PZ_MTEST --show -a controlled:qsize=1 controlled:qsize=3
        python -m ibeis.dev -e draw_rank_cdf -t candidacy_baseline --db PZ_MTEST -a controlled --show
        python -m ibeis.dev -e draw_rank_cdf -t candidacy_baseline --db PZ_Master0 --controlled --show
        python -m ibeis.dev -e draw_rank_cdf -t candidacy_namescore --db PZ_Master0 --controlled --show

        python -m ibeis.dev -e draw_rank_cdf -t candidacy_namescore --db PZ_MTEST --controlled --show

        python -m ibeis.dev -e draw_rank_cdf -t candidacy_baseline --db PZ_MTEST -a controlled --show

        python -m ibeis -tm exptdraw --exec-draw_rank_cdf -t candidacy_baseline -a controlled --db PZ_MTEST --show

        python -m ibeis.dev -e draw_rank_cdf -t candidacy_invariance -a controlled --db PZ_Master0   --save invar_cumhist_{db}_a_{a}_t_{t}.png --dpath=~/code/ibeis/results  --adjust=.15 --dpi=256 --clipwhite --diskshow


    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> from ibeis.init import main_helpers
        >>> ibs, test_result = main_helpers.testdata_expts('PZ_MTEST')
        >>> result = draw_rank_cdf(ibs, test_result)
        >>> ut.show_if_requested()
        >>> print(result)
    """
    import plottool as pt
    #cdf_list, edges = test_result.get_rank_cumhist(bins='dense')
    cfgx2_cumhist_percent, edges = test_result.get_rank_percentage_cumhist(bins='dense')
    label_list = test_result.get_short_cfglbls()
    label_list = [ut.scalar_str(percent, precision=2) + '% - ' + label
                  for percent, label in zip(cfgx2_cumhist_percent.T[0], label_list)]
    color_list = pt.distinct_colors(len(label_list))
    marker_list = pt.distinct_markers(len(label_list))
    test_cfgx_slice = ut.get_argval('--test_cfgx_slice', type_='fuzzy_subset', default=None)
    if test_cfgx_slice is not None:
        print('test_cfgx_slice = %r' % (test_cfgx_slice,))
        cfgx2_cumhist_percent = np.array(ut.list_take(cfgx2_cumhist_percent,
                                                      test_cfgx_slice))
        label_list = ut.list_take(label_list, test_cfgx_slice)
        color_list = ut.list_take(color_list, test_cfgx_slice)
        marker_list = ut.list_take(marker_list, test_cfgx_slice)
    # Order cdf list by rank0
    sortx = cfgx2_cumhist_percent.T[0].argsort()[::-1]
    label_list = ut.list_take(label_list, sortx)
    cfgx2_cumhist_percent = np.array(ut.list_take(cfgx2_cumhist_percent, sortx))
    color_list = ut.list_take(color_list, sortx)
    marker_list = ut.list_take(marker_list, sortx)
    #
    figtitle = ('Cumulative Rank Histogram\n')
    figtitle += ' ' + test_result.get_title_aug()

    test_result.print_unique_annot_config_stats(ibs)

    import vtool as vt
    # Find where the functions no longer change
    freq_deriv = np.diff(cfgx2_cumhist_percent.T[:-1].T)
    reverse_deriv_cumsum = freq_deriv[:, ::-1].cumsum(axis=0)
    reverse_changing_pos = np.array(ut.replace_nones(
        vt.find_first_true_indices(reverse_deriv_cumsum > 0), np.nan))
    nonzero_poses = (len(cfgx2_cumhist_percent.T) - 1) - reverse_changing_pos
    maxrank = np.nanmax(nonzero_poses)

    maxrank = 5
    #maxrank = ut.get_argval('--maxrank', type_=int, default=maxrank)

    if maxrank is not None:
        maxpos = min(len(cfgx2_cumhist_percent.T), maxrank)
        cfgx2_cumhist_short = cfgx2_cumhist_percent[:, 0:maxpos]
        edges_short = edges[0:min(len(edges), maxrank + 1)]

    USE_ZOOM = ut.get_argflag('--use-zoom')
    pnum_ = pt.make_pnum_nextgen(nRows=USE_ZOOM + 1, nCols=1)

    fnum = pt.ensure_fnum(None)

    cumhistkw = dict(
        xlabel='rank', ylabel='% queries ≤ rank', color_list=color_list,
        marker_list=marker_list, fnum=fnum, legend_loc='lower right',
        num_yticks=8, ymax=100, ymin=30, ypad=.5, xpad=.05, **FONTKW)

    pt.plot_rank_cumhist(
        cfgx2_cumhist_short, edges=edges_short, label_list=label_list,
        num_xticks=maxrank, use_legend=True, pnum=pnum_(), **cumhistkw)

    if USE_ZOOM:
        ax1 = pt.gca()
        pt.plot_rank_cumhist(
            cfgx2_cumhist_percent, edges=edges, label_list=label_list,
            num_xticks=maxrank, use_legend=False, pnum=pnum_(), **cumhistkw)
        ax2 = pt.gca()
        pt.zoom_effect01(ax1, ax2, 1, maxrank, fc='w')
    pt.set_figtitle(figtitle, size=14)
    if ut.get_argflag('--contextadjust'):
        pt.adjust_subplots(left=.05, bottom=.08, wspace=.0, hspace=.15)
    #pt.set_figtitle(figtitle, size=10)


def make_metadata_custom_api(metadata):
    r"""
    CommandLine:
        python -m ibeis.experiments.experiment_drawing --test-make_metadata_custom_api --show

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> import guitool
        >>> guitool.ensure_qapp()
        >>> metadata_fpath = '/media/raid/work/Elephants_drop1_ears/_ibsdb/figures/result_metadata.shelf'
        >>> metadata = experiment_storage.ResultMetadata(metadata_fpath, autoconnect=True)
        >>> wgt = make_metadata_custom_api(metadata)
        >>> ut.quit_if_noshow()
        >>> wgt.show()
        >>> wgt.raise_()
        >>> guitool.qtapp_loop(wgt, frequency=100)
    """
    import guitool
    from guitool.__PYQT__ import QtCore

    class MetadataViewer(guitool.APIItemWidget):
        def __init__(wgt, parent=None, tblnice='Result Metadata Viewer', **kwargs):
            guitool.APIItemWidget.__init__(wgt, parent=parent, tblnice=tblnice, **kwargs)
            wgt.connect_signals_and_slots()

        @guitool.slot_(QtCore.QModelIndex)
        def _on_doubleclick(wgt, qtindex):
            print('[wgt] _on_doubleclick: ')
            col = qtindex.column()
            if wgt.api.col_edit_list[col]:
                print('do nothing special for editable columns')
                return
            model = qtindex.model()
            colname = model.get_header_name(col)
            if colname.endswith('fpath'):
                print('showing fpath')
                fpath = model.get_header_data(colname, qtindex)
                ut.startfile(fpath)

        def connect_signals_and_slots(wgt):
            #wgt.view.clicked.connect(wgt._on_click)
            wgt.view.doubleClicked.connect(wgt._on_doubleclick)
            #wgt.view.pressed.connect(wgt._on_pressed)
            #wgt.view.activated.connect(wgt._on_activated)

    guitool.ensure_qapp()
    #cfgstr_list = metadata
    col_name_list, column_list = metadata.get_square_data()

    # Priority of column names
    colname_priority = ['qaids', 'qx2_gt_rank', 'qx2_gt_timedelta',
                        'qx2_gf_timedelta',  'analysis_fpath',
                        'qx2_gt_raw_score', 'qx2_gf_raw_score']
    colname_priority += sorted(ut.setdiff_ordered(col_name_list, colname_priority))
    sortx = ut.priority_argsort(col_name_list, colname_priority)
    col_name_list = ut.list_take(col_name_list, sortx)
    column_list = ut.list_take(column_list, sortx)

    col_lens = list(map(len, column_list))
    print('col_name_list = %r' % (col_name_list,))
    print('col_lens = %r' % (col_lens,))
    assert len(col_lens) > 0, 'no columns'
    assert col_lens[0] > 0, 'no rows'
    assert all([len_ == col_lens[0] for len_ in col_lens]), 'inconsistant data'
    col_types_dict = {}
    col_getter_dict = dict(zip(col_name_list, column_list))
    col_bgrole_dict = {}
    col_ider_dict = {}
    col_setter_dict = {}
    col_nice_dict = {name: name.replace('qx2_', '') for name in col_name_list}
    col_nice_dict.update({
        'qx2_gt_timedelta': 'GT TimeDelta',
        'qx2_gf_timedelta': 'GF TimeDelta',
        'qx2_gt_rank': 'GT Rank',
    })
    editable_colnames = []
    sortby = 'qaids'
    get_thumb_size = lambda: 128
    col_width_dict = {}
    custom_api = guitool.CustomAPI(
        col_name_list, col_types_dict, col_getter_dict,
        col_bgrole_dict, col_ider_dict, col_setter_dict,
        editable_colnames, sortby, get_thumb_size,
        sort_reverse=True,
        col_width_dict=col_width_dict,
        col_nice_dict=col_nice_dict
    )
    #headers = custom_api.make_headers(tblnice='results')
    #print(ut.dict_str(headers))
    wgt = MetadataViewer()
    wgt.connect_api(custom_api)
    return wgt


def make_test_result_custom_api(ibs, test_result):
    import guitool
    guitool.ensure_qapp()
    cfgx = 0
    cfgres_info = test_result.cfgx2_cfgresinfo[cfgx]
    qaids = test_result.qaids
    gt_aids = cfgres_info['qx2_gt_aid']
    gf_aids = cfgres_info['qx2_gf_aid']
    qx2_gt_timedelta = ibs.get_annot_pair_timdelta(qaids, gt_aids)
    qx2_gf_timedelta = ibs.get_annot_pair_timdelta(qaids, gf_aids)
    col_name_list = [
        'qaids',
        'qx2_gt_aid',
        'qx2_gf_aid',
        'qx2_gt_timedelta',
        'qx2_gf_timedelta',
    ]
    col_types_dict = {}
    col_getter_dict = {}
    col_getter_dict.update(**cfgres_info)
    col_getter_dict['qaids'] = test_result.qaids
    col_getter_dict['qx2_gt_timedelta'] = qx2_gt_timedelta
    col_getter_dict['qx2_gf_timedelta'] = qx2_gf_timedelta
    col_bgrole_dict = {}
    col_ider_dict = {}
    col_setter_dict = {}
    editable_colnames = []
    sortby = 'qaids'
    get_thumb_size = lambda: 128
    col_width_dict = {}

    custom_api = guitool.CustomAPI(
        col_name_list, col_types_dict, col_getter_dict,
        col_bgrole_dict, col_ider_dict, col_setter_dict,
        editable_colnames, sortby, get_thumb_size, True, col_width_dict)
    #headers = custom_api.make_headers(tblnice='results')
    #print(ut.dict_str(headers))
    wgt = guitool.APIItemWidget()
    wgt.connect_api(custom_api)
    return wgt


def _show_chip(ibs, aid, individual_results_figdir, prefix, rank=None, in_image=False, seen=set([]), config2_=None, **dumpkw):
    print('[PRINT_RESULTS] show_chip(aid=%r) prefix=%r' % (aid, prefix))
    import plottool as pt
    from ibeis import viz
    # only dump a chip that hasn't been dumped yet
    if aid in seen:
        print('[PRINT_RESULTS] SEEN SKIPPING')
        return
    fulldir = join(individual_results_figdir, dumpkw['subdir'])
    if DUMP_PROBCHIP:
        # just copy it
        probchip_fpath = ibs.get_annot_probchip_fpath([aid], config2_=config2_)[0]
        ut.copy(probchip_fpath, fulldir, overwrite=False)
    if DUMP_REGCHIP:
        chip_fpath = ibs.get_annot_chip_fpath([aid], config2_=config2_)[0]
        ut.copy(chip_fpath, fulldir, overwrite=False)

    viz.show_chip(ibs, aid, in_image=in_image, config2_=config2_)
    if rank is not None:
        prefix += 'rank%d_' % rank
    fname = prefix + ibs.annotstr(aid)
    df2.set_figtitle(fname)
    seen.add(aid)
    if ut.VERBOSE:
        print('[expt] dumping fig to individual_results_figdir=%s' % individual_results_figdir)
    #fpath_clean = ph.dump_figure(individual_results_figdir, **dumpkw)
    fpath_ = join(individual_results_figdir, fname)
    pt.gcf().savefig(fpath_)
    return fpath_


class IndividualResultsCopyTaskQueue(object):
    def __init__(self):
        self.cp_task_list = []

    def append_copy_task(self, fpath_orig, dstdir=None):
        """ helper which copies a summary figure to root dir """
        fname_orig, ext = splitext(basename(fpath_orig))
        outdir = dirname(fpath_orig)
        fdir_clean, cfgdir = split(outdir)
        if dstdir is None:
            dstdir = fdir_clean
        #aug = cfgdir[0:min(len(cfgdir), 10)]
        aug = cfgdir
        fname_fmt = '{aug}_{fname_orig}{ext}'
        fmt_dict = {'aug': aug, 'fname_orig': fname_orig, 'ext': ext}
        fname_clean = ut.long_fname_format(fname_fmt, fmt_dict, ['fname_orig'], max_len=128)
        fdst_clean = join(dstdir, fname_clean)
        self.cp_task_list.append((fpath_orig, fdst_clean))

    def flush_copy_tasks(self):
        # Execute all copy tasks and empty the lists
        print('[DRAW_RESULT] copying %r summaries' % (len(self.cp_task_list)))
        for src, dst in self.cp_task_list:
            ut.copy(src, dst, verbose=False)
        del self.cp_task_list[:]


@profile
def draw_case_timedeltas(ibs, test_result, metadata=None):
    r"""

    CommandLine:
        python -m ibeis.dev -e draw_case_timedeltas

        python -m ibeis.dev -e timedelta_hist -t baseline -a uncontrolled controlled:force_const_size=True uncontrolled:force_const_size=True --consistent --db PZ_Master1 --show
        python -m ibeis.dev -e timedelta_hist -t baseline -a uncontrolled controlled:sample_rule_ref=max_timedelta --db PZ_Master1 --show --aidcfginfo


    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> from ibeis.init import main_helpers
        >>> ibs, test_result = main_helpers.testdata_expts('PZ_MTEST')
        >>> metadata = None
        >>> draw_case_timedeltas(ibs, test_result, metadata)
        >>> ut.show_if_requested()
    """
    #category_poses = test_result.partition_case_types()
    # TODO: Split up into cfgxs
    plotkw = FONTKW.copy()
    plotkw['markersize'] = 12
    plotkw['marker_list'] = []
    #plotkw['linestyle'] = '--'
    import plottool as pt

    test_result.print_unique_annot_config_stats(ibs)

    truth2_prop, is_success, is_failure = test_result.get_truth2_prop()
    X_data_list = []
    X_label_list = []
    cfgx2_shortlbl = test_result.get_short_cfglbls()
    TRUEPOS = ut.get_argflag('--falsepos')
    for cfgx, lbl in enumerate(cfgx2_shortlbl):
        gt_f_td = truth2_prop['gt']['timedelta'].T[cfgx][is_failure.T[cfgx]]  # NOQA
        gf_f_td = truth2_prop['gf']['timedelta'].T[cfgx][is_failure.T[cfgx]]  # NOQA
        gt_s_td = truth2_prop['gt']['timedelta'].T[cfgx][is_success.T[cfgx]]
        gf_s_td = truth2_prop['gf']['timedelta'].T[cfgx][is_success.T[cfgx]]  # NOQA
        #X_data_list  += [np.append(gt_f_td, gt_s_td), np.append(gf_f_td, gf_s_td)]
        #X_label_list += ['GT ' + lbl, 'GF ' + lbl]
        #X_data_list  += [gt_s_td, gt_f_td, gf_f_td, gf_s_td]
        #X_label_list += ['TP ' + lbl, 'FN ' + lbl, 'TN ' + lbl, 'FP ' + lbl]
        if TRUEPOS:
            X_data_list  += [
                gf_s_td
            ]
            X_label_list += [
                'FP ' + lbl
            ]
        else:
            X_data_list  += [
                gt_s_td,
                #gf_s_td
            ]
            X_label_list += [
                'TP ' + lbl,
                #'FP ' + lbl
            ]
        plotkw['marker_list'] += pt.distinct_markers(1, style='polygon',
                                                     offset=cfgx,
                                                     total=len(cfgx2_shortlbl))
        #plotkw['marker_list'] += pt.distinct_markers(1, style='astrisk', offset=cfgx, total=len(cfgx2_shortlbl))

    # TODO WRAP IN VTOOL
    # LEARN MULTI PDF
    #gridsize = 1024
    #adjust = 64
    numnan_list = [(~np.isfinite(X)).sum() for X in X_data_list]
    xdata_list = [X[~np.isnan(X)] for X in X_data_list]
    #import vtool as vt
    #xdata_pdf_list = [vt.estimate_pdf(xdata, gridsize=gridsize, adjust=adjust) for xdata in xdata_list]  # NOQA
    #min_score = min([xdata.min() for xdata in xdata_list])
    max_score = max([xdata.max() for xdata in xdata_list])
    #xdata_domain = np.linspace(min_score, max_score, gridsize)  # NOQA
    #pxdata_list = [pdf.evaluate(xdata_domain) for pdf in xdata_pdf_list]

    ## VISUALIZE MULTI PDF

    #import vtool as vt
    #encoder = vt.ScoreNormalizerUnsupervised(gt_f_td)
    #encoder.visualize()

    #import plottool as pt
    ##is_timedata = False
    #is_timedelta = True
    #pt.plot_probabilities(pxdata_list, X_label_list, xdata=xdata_domain)
    #ax = pt.gca()

    import datetime

    bins = [
        datetime.timedelta(seconds=0).total_seconds(),
        datetime.timedelta(minutes=1).total_seconds(),
        datetime.timedelta(hours=1).total_seconds(),
        datetime.timedelta(days=1).total_seconds(),
        datetime.timedelta(weeks=1).total_seconds(),
        datetime.timedelta(days=356).total_seconds(),
        #np.inf,
        max(datetime.timedelta(days=356 * 10).total_seconds(), max_score + 1),
    ]

    # HISTOGRAM
    #if False:
    freq_list = [np.histogram(xdata, bins)[0] for xdata in xdata_list]
    timedelta_strs = [ut.get_timedelta_str(datetime.timedelta(seconds=b), exclude_zeros=True) for b in bins]
    bin_labels = [l + ' - ' + h for l, h in ut.iter_window(timedelta_strs)]
    bin_labels[-1] = '> 1 year'
    bin_labels[0] = '< 1 minute'
    WITH_NAN = True
    if WITH_NAN:
        freq_list = [np.append(freq, [numnan]) for freq, numnan in zip(freq_list , numnan_list)]
        bin_labels += ['nan']

    # Convert to percent
    freq_list = [100 * freq / len(is_success) for freq in freq_list]

    xints = np.arange(len(bin_labels))

    PIE = True

    if PIE:
        fnum = 1
        pt.figure(fnum=fnum)
        pnum_ = pt.make_pnum_nextgen(*pt.get_square_row_cols(len(freq_list)))
        bin_labels[0]

        for count, freq in enumerate(freq_list):
            pt.figure(fnum=fnum, pnum=pnum_())
            pt.plt.pie(freq, explode=[0] * len(freq), autopct='%1.1f%%', labels=bin_labels)
            ax = pt.gca()
            ax.set_xlabel(X_label_list[count])
        if ut.get_argflag('--contextadjust'):
            pt.adjust_subplots2(left=.08, bottom=.1, top=.9, wspace=.3, hspace=.1)
    else:
        pt.multi_plot(xints, freq_list, label_list=X_label_list, xpad=1, ypad=.5, **plotkw)
        ax = pt.gca()

        xtick_labels = [''] + bin_labels + ['']

        ax.set_xticklabels(xtick_labels)
        ax.set_xlabel('timedelta')
        #ax.set_ylabel('Frequency')
        ax.set_ylabel('% true positives')
        ax.set_title('Timedelta histogram of correct matches\n' + test_result.get_title_aug())
        pt.gcf().autofmt_xdate()

        if ut.get_argflag('--contextadjust'):
            pt.adjust_subplots(left=.2, bottom=.2, wspace=.0, hspace=.15)


@profile
def draw_individual_cases(ibs, test_result, metadata=None):
    r"""
    Args:
        ibs (IBEISController):  ibeis controller object
        test_result (?):
        metadata (None): (default = None)

    CommandLine:
        python -m ibeis.dev -e draw_individual_cases --figdir=individual_results
        python -m ibeis.dev -e draw_individual_cases --db PZ_Master1 -a controlled -t default --figdir=figures --vf --vh2 --show
        python -m ibeis.dev -e draw_individual_cases --db PZ_Master1 -a varysize_pzm:dper_name=[1,2],dsize=1500 -t candidacy_k:K=1 --figdir=figures --vf --vh2 --show
        python -m ibeis.dev -e draw_individual_cases --db PZ_Master1 -a varysize_pzm:dper_name=[1,2],dsize=1500 -t candidacy_k:K=1 --figdir=figures --vf --vh2
        python -m ibeis.dev -e draw_individual_cases --db PZ_MTEST -a varysize_pzm:dper_name=[1,2] -t candidacy_k:K=1 --figdir=figures --vf --vh --show
        python -m ibeis.dev -e draw_individual_cases --db PZ_MTEST --vf --vh --show -a uncontrolled -t default:K=[1,2]
        python -m ibeis.dev -e draw_individual_cases -t baseline -a controlled --db PZ_Master1 \


    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> from ibeis.init import main_helpers
        >>> ibs, test_result = main_helpers.testdata_expts('PZ_MTEST')
        >>> metadata = None
        >>> analysis_fpath_list = draw_individual_cases(ibs, test_result, metadata)
        >>> cmdname = ibs.get_dbname() + 'Results'
        >>> latex_block  = ut.get_latex_figure_str2(analysis_fpath_list, cmdname, nCols=1)
        >>> ut.print_code(latex_block, 'latex')
        >>> #ut.show_if_requested()
    """
    import plottool as pt
    cfgx2_qreq_ = test_result.cfgx2_qreq_

    # Get selected rows and columns for individual rank investigation
    #qaids = test_result.qaids

    show_kwargs = {
        'N': 3,
        'ori': True,
        'ell_alpha': .9,
    }

    cpq = IndividualResultsCopyTaskQueue()

    figdir = ibs.get_fig_dir()
    figdir = ut.truepath(ut.get_argval(('--figdir', '--dpath'), type_=str, default=figdir))
    figdir = join(figdir, 'cases_' + test_result.get_fname_aug(withinfo=False))
    ut.ensuredir(figdir)

    if ut.is_developer() or ut.get_argflag(('--view-fig-directory', '--vf')):
        ut.view_directory(figdir)

    DRAW_ANALYSIS = True
    DRAW_BLIND = False and not SHOW
    #DUMP_EXTRA = ut.get_argflag('--dump-extra')
    #DRAW_QUERY_CHIP = DUMP_EXTRA
    #DRAW_QUERY_GROUNDTRUTH = DUMP_EXTRA
    #DRAW_QUERY_RESULT_CONTEXT  = DUMP_EXTRA

    # Common directory
    individual_results_figdir = join(figdir, 'individual_results')
    ut.ensuredir(individual_results_figdir)

    if DRAW_ANALYSIS:
        top_rank_analysis_dir = join(figdir, 'top_rank_analysis')
        ut.ensuredir(top_rank_analysis_dir)

    if DRAW_BLIND:
        blind_results_figdir  = join(figdir, 'blind_results')
        ut.ensuredir(blind_results_figdir)

    #_viewkw = dict(view_interesting=True)
    _viewkw = {}

    #=================================
    # TODO:
    # Get a better (stratified) sample of the hard cases that incorporates the known failure cases
    # (Show a photobomb, scenery match, etc...)
    # This is just one config, because showing everything should also be an
    # option so we can find these errors
    #-------------
    # TODO;
    # Time statistics on incorrect results
    #=================================
    sel_rows, sel_cols, flat_case_labels = get_individual_result_sample(test_result, **_viewkw)
    if flat_case_labels is None:
        flat_case_labels = [None] * len(sel_rows)

    qaids = test_result.get_common_qaids()
    ibs.get_annot_semantic_uuids(ut.list_take(qaids, sel_rows))  # Ensure semantic uuids are in the APP cache.
    #samplekw = dict(per_group=5)
    #case_pos_list = test_result.get_case_positions('failure', samplekw=samplekw)
    #failure_qx_list = ut.unique_keep_order2(case_pos_list.T[0])
    #sel_rows = (np.array(failure_qx_list).tolist())
    #sel_cols = (list(range(test_result.nConfig)))

    custom_actions = [('present', ['s'], 'present', pt.present)]

    analysis_fpath_list = []

    def reset():
        if not SHOW:
            try:
                pt.fig_presenter.reset()
            except Exception as ex:
                if ut.VERBOSE:
                    ut.prinex(ex)
                pass

    #overwrite = False
    overwrite = True

    cfgx2_shortlbl = test_result.get_short_cfglbls()
    for count, r in enumerate(ut.InteractiveIter(sel_rows, enabled=SHOW, custom_actions=custom_actions)):
        case_labels = flat_case_labels[count]
        print('case_labels = %r' % (case_labels,))
        qreq_list = ut.list_take(cfgx2_qreq_, sel_cols)
        #qres_list = [load_qres(ibs, qaids[r], qreq_) for qreq_ in qreq_list]
        # TODO: try to get away with not reloading query results or loading
        # them in batch if possible
        # It actually doesnt take that long. the drawing is what hurts
        qres_list = [qreq_.load_cached_qres(qaids[r]) for qreq_ in qreq_list]

        for cfgx, qres, qreq_ in zip(sel_cols, qres_list, qreq_list):
            fnum = cfgx if SHOW else 1
            # Get row and column index
            cfgstr = test_result.get_cfgstr(cfgx)
            query_lbl = cfgx2_shortlbl[cfgx]
            if False:
                qres_dpath = qres.get_fname(ext='', hack27=True)
            else:
                qres_dpath = 'qaid={qaid}'.format(qaid=qres.qaid)
            individ_results_dpath = join(individual_results_figdir, qres_dpath)
            ut.ensuredir(individ_results_dpath)
            # Draw Result
            # try to shorten query labels a bit
            query_lbl = query_lbl.replace(' ', '').replace('\'', '')
            qres_fname = query_lbl + '.png'
            #qres.show(ibs, 'analysis', figtitle=query_lbl, fnum=fnum, **show_kwargs)

            # SHOW ANALYSIS
            show_kwargs['show_query'] = False
            show_kwargs['viz_name_score'] = True
            show_kwargs['show_timedelta'] = True
            show_kwargs['show_gf'] = True
            if DRAW_ANALYSIS:
                analysis_fpath = join(individ_results_dpath, qres_fname)
                #print('analysis_fpath = %r' % (analysis_fpath,))
                if SHOW or overwrite or not ut.checkpath(analysis_fpath):
                    if SHOW:
                        qres.ishow_analysis(ibs, figtitle=query_lbl, fnum=fnum, annot_mode=1, qreq_=qreq_, **show_kwargs)
                    else:
                        qres.show_analysis(ibs, figtitle=query_lbl, fnum=fnum, annot_mode=1, qreq_=qreq_, **show_kwargs)

                    # So hacky
                    if ut.get_argflag('--tight'):
                        #pt.plt.tight_layout()
                        #pt.plt.tight_layout()
                        #pt.plt.tight_layout()
                        #pt.plt.tight_layout()
                        #pt.plt.tight_layout()
                        pass
                    #pt.adjust_subplots2(top=.9)
                    #pt.adjust_subplots2(use_argv=True, hspace=0)
                    #pt.adjust_subplots(.01, .01, .98, .9, .05, .15)
                    pt.gcf().savefig(analysis_fpath)
                    import vtool as vt
                    vt.clipwhite_ondisk(analysis_fpath, analysis_fpath, verbose=ut.VERBOSE)
                    cpq.append_copy_task(analysis_fpath, top_rank_analysis_dir)
                    #fig, fnum = prepare_figure_for_save(fnum, dpi, figsize, fig)
                    #analysis_fpath_ = pt.save_figure(fpath=analysis_fpath, **dumpkw)
                    #reset()
                analysis_fpath_list.append(analysis_fpath)
                if metadata is not None:
                    metadata.set_global_data(cfgstr, qres.qaid, 'analysis_fpath', analysis_fpath)

            # BLIND CASES - draws results without labels to see if we can determine what happened using doubleblind methods
            if DRAW_BLIND:
                pt.clf()
                best_gt_aid = qres.get_top_groundtruth_aid(ibs=ibs)
                qres.show_name_matches(ibs, best_gt_aid,
                                       show_matches=False,
                                       show_name_score=False,
                                       show_name_rank=False,
                                       show_annot_score=False, fnum=fnum,
                                       qreq_=qreq_, **show_kwargs)
                blind_figtitle = 'BLIND ' + query_lbl
                pt.set_figtitle(blind_figtitle)
                blind_fpath = join(individ_results_dpath, blind_figtitle) + '.png'
                pt.gcf().savefig(blind_fpath)
                #blind_fpath = pt.custom_figure.save_figure(fpath=blind_fpath, **dumpkw)
                cpq.append_copy_task(blind_fpath, blind_results_figdir)
                if metadata is not None:
                    metadata.set_global_data(cfgstr, qres.qaid, 'blind_fpath', blind_fpath)
                #reset()

            # REMOVE DUMP_FIG
            #extra_kw = dict(config2_=qreq_.get_external_query_config2(), subdir=subdir, **dumpkw)
            #if DRAW_QUERY_CHIP:
            #    _show_chip(ibs, qres.qaid, individual_results_figdir, 'QUERY_', **extra_kw)
            #    _show_chip(ibs, qres.qaid, individual_results_figdir, 'QUERY_CXT_', in_image=True, **extra_kw)

            #if DRAW_QUERY_GROUNDTRUTH:
            #    gtaids = ibs.get_annot_groundtruth(qres.qaid)
            #    for aid in gtaids:
            #        rank = qres.get_aid_ranks(aid)
            #        _show_chip(ibs, aid, individual_results_figdir, 'GT_CXT_', rank=rank, in_image=True, **extra_kw)

            #if DRAW_QUERY_RESULT_CONTEXT:
            #    topids = qres.get_top_aids(num=3)
            #    for aid in topids:
            #        rank = qres.get_aid_ranks(aid)
            #        _show_chip(ibs, aid, individual_results_figdir, 'TOP_CXT_', rank=rank, in_image=True, **extra_kw)

        # if some condition of of batch sizes
        flush_freq = 4
        if count % flush_freq == (flush_freq - 1):
            cpq.flush_copy_tasks()

    # Copy summary images to query_analysis folder
    cpq.flush_copy_tasks()
    return analysis_fpath_list


def get_individual_result_sample(test_result,
                                 view_all=ut.get_argflag(('--view-all', '--va')),
                                 view_hard=ut.get_argflag(('--view-hard', '--vh')),
                                 view_hard2=ut.get_argflag(('--view-hard2', '--vh2')),
                                 view_easy=ut.get_argflag(('--view-easy', '--vz')),
                                 view_interesting=ut.get_argflag(('--view-interesting', '--vn')),
                                 **kwargs):
    """
    The selected rows are the query annotation you are interested in viewing
    The selected cols are the parameter configuration you are interested in viewing
    """
    cfg_list = test_result.cfg_list
    #qaids = test_result.qaids
    qaids = test_result.get_common_qaids()

    #sel_cols = params.args.sel_cols  # FIXME
    #sel_rows = params.args.sel_rows  # FIXME
    #sel_cols = [] if sel_cols is None else sel_cols
    #sel_rows = [] if sel_rows is None else sel_rows
    sel_rows = []
    sel_cols = []
    flat_case_labels = None
    if ut.NOT_QUIET:
        print('remember to inspect with --show --sel-rows (-r) and --sel-cols (-c) ')
        print('other options:')
        print('   --vf - view figure dir')
        print('   --va - view all')
        print('   --vh - view hard')
        print('   --ve - view easy')
        print('   --vn - view iNteresting')
        print('   --hs - hist sample')
        print('   --gv, --guiview - gui result inspection')
    if len(sel_rows) > 0 and len(sel_cols) == 0:
        sel_cols = list(range(len(cfg_list)))
    if len(sel_cols) > 0 and len(sel_rows) == 0:
        sel_rows = list(range(len(qaids)))
    if view_all:
        sel_rows = list(range(len(qaids)))
        sel_cols = list(range(len(cfg_list)))
    if view_hard:
        new_hard_qx_list = test_result.get_new_hard_qx_list()
        sel_rows.extend(np.array(new_hard_qx_list).tolist())
        sel_cols.extend(list(range(len(cfg_list))))
    # sample-cases

    def convert_case_pos_to_cfgx(case_pos_list, case_labels_list):
        # Convert to all cfgx format
        qx_list = ut.unique_keep_order2(np.array(case_pos_list).T[0])
        ut.dict_take(ut.group_items(case_pos_list, case_pos_list.T[0]), qx_list)
        grouped_labels = ut.dict_take(ut.group_items(case_labels_list, case_pos_list.T[0]), qx_list)
        flat_case_labels = list(map(ut.unique_keep_order2, map(ut.flatten, grouped_labels)))
        new_rows = np.array(qx_list).tolist()
        new_cols = list(range(len(cfg_list)))
        return new_rows, new_cols, flat_case_labels

    view_differ_cases = ut.get_argflag(('--diff-cases', '--dc'))
    if view_differ_cases:
        # Cases that passed on config but failed another
        case_pos_list, case_labels_list = test_result.case_type_sample(1, with_success=True, min_success_diff=1)
        new_rows, new_cols, flat_case_labels = convert_case_pos_to_cfgx(case_pos_list, case_labels_list)
        sel_rows.extend(new_rows)
        sel_cols.extend(new_cols)

    view_cases = ut.get_argflag(('--view-cases', '--vc'))
    if view_cases:
        case_pos_list, case_labels_list = test_result.case_type_sample(1, with_success=False)
        new_rows, new_cols, flat_case_labels = convert_case_pos_to_cfgx(case_pos_list, case_labels_list)
        sel_rows.extend(new_rows)
        sel_cols.extend(new_cols)

    if view_hard2:
        # TODO handle returning case_pos_list
        #samplekw = ut.argparse_dict(dict(per_group=5))
        samplekw = ut.argparse_dict(dict(per_group=None))
        case_pos_list = test_result.get_case_positions(mode='failure', samplekw=samplekw)
        failure_qx_list = ut.unique_keep_order2(case_pos_list.T[0])
        sel_rows.extend(np.array(failure_qx_list).tolist())
        sel_cols.extend(list(range(len(cfg_list))))
    if view_easy:
        new_hard_qx_list = test_result.get_new_hard_qx_list()
        new_easy_qx_list = np.setdiff1d(np.arange(len(qaids)), new_hard_qx_list).tolist()
        sel_rows.extend(new_easy_qx_list)
        sel_cols.extend(list(range(len(cfg_list))))
    if view_interesting:
        interesting_qx_list = test_result.get_interesting_ranks()
        sel_rows.extend(interesting_qx_list)
        # TODO: grab the best scoring and most interesting configs
        if len(sel_cols) == 0:
            sel_cols.extend(list(range(len(cfg_list))))
    if kwargs.get('hist_sample', ut.get_argflag(('--hs', '--hist-sample'))):
        # Careful if there is more than one config
        config_rand_bin_qxs = test_result.get_rank_histogram_qx_sample(size=10)
        sel_rows = np.hstack(ut.flatten(config_rand_bin_qxs))
        # TODO: grab the best scoring and most interesting configs
        if len(sel_cols) == 0:
            sel_cols.extend(list(range(len(cfg_list))))

    sel_rows = ut.unique_keep_order2(sel_rows)
    sel_cols = ut.unique_keep_order2(sel_cols)
    sel_cols = list(sel_cols)
    sel_rows = list(sel_rows)

    print('len(sel_rows) = %r' % (len(sel_rows),))
    print('len(sel_cols) = %r' % (len(sel_cols),))

    sel_rowxs = ut.get_argval('-r', type_=list, default=None)
    sel_colxs = ut.get_argval('-c', type_=list, default=None)
    print('sel_rowxs = %r' % (sel_rowxs,))
    print('sel_colxs = %r' % (sel_colxs,))

    if sel_rowxs is not None:
        sel_rows = ut.list_take(sel_rows, sel_rowxs)
        print('sel_rows = %r' % (sel_rows,))

    if sel_colxs is not None:
        sel_cols = ut.list_take(sel_cols, sel_colxs)
        print('sel_cols = %r' % (sel_cols,))

    print('Filtered')
    print('len(sel_rows) = %r' % (len(sel_rows),))
    print('len(sel_cols) = %r' % (len(sel_cols),))

    return sel_rows, sel_cols, flat_case_labels


@profile
def draw_results(ibs, test_result):
    r"""
    Draws results from an experiment harness run.
    Rows store different qaids (query annotation ids)
    Cols store different configurations (algorithm parameters)

    Args:
        test_result (experiment_storage.TestResult):

    CommandLine:
        python dev.py -t custom:rrvsone_on=True,constrained_coeff=0 custom --qaid 12 --db PZ_MTEST --show --va
        python dev.py -t custom:rrvsone_on=True,constrained_coeff=.3 custom --qaid 12 --db PZ_MTEST --show --va --noqcache
        python dev.py -t custom:rrvsone_on=True custom --qaid 4 --db PZ_MTEST --show --va --noqcache

        python dev.py -t custom:rrvsone_on=True,grid_scale_factor=1 custom --qaid 12 --db PZ_MTEST --show --va --noqcache
        python dev.py -t custom:rrvsone_on=True,grid_scale_factor=1,grid_steps=1 custom --qaid 12 --db PZ_MTEST --show --va --noqcache

    CommandLine:
        python dev.py -t best --db seals2 --allgt --vz --fig-dname query_analysis_easy --show
        python dev.py -t best --db seals2 --allgt --vh --fig-dname query_analysis_hard --show

        python dev.py -t pyrscale --db PZ_MTEST --allgt --vn --fig-dname query_analysis_interesting --show
        python dev.py -t pyrscale --db testdb3 --allgt --vn --fig-dname query_analysis_interesting --vf
        python dev.py -t pyrscale --db testdb3 --allgt --vn --fig-dname query_analysis_interesting --vf --quality


        python -m ibeis.experiments.experiment_drawing --test-draw_results --show --vn
        python -m ibeis.experiments.experiment_drawing --test-draw_results --show --vn --db PZ_MTEST
        python -m ibeis.experiments.experiment_drawing --test-draw_results --show --db PZ_MTEST --draw-rank-cdf

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.experiments.experiment_drawing import *  # NOQA
        >>> from ibeis.init import main_helpers
        >>> ibs, test_result = main_helpers.testdata_expts('PZ_MTEST')
        >>> # execute function
        >>> result = draw_results(ibs, test_result)
        >>> # verify results
        >>> print(result)
    """
    print(' --- DRAW RESULTS ---')

    # It is very inefficient to turn off caching when view_all is true
    if not mc4.USE_CACHE:
        print('WARNING: view_all specified with USE_CACHE == False')
        print('WARNING: we will try to turn cache on when reloading results')
        #mc4.USE_CACHE = True

    figdir = ibs.get_fig_dir()
    ut.ensuredir(figdir)

    if ut.get_argflag(('--view-fig-directory', '--vf')):
        ut.view_directory(figdir)

    figdir_suffix = ut.get_argval('--fig-dname', type_=str, default=None)
    if figdir_suffix is not None:
        figdir = join(figdir, figdir_suffix)
        ut.ensuredir(figdir)
    #gx2_gt_timedelta
    #    cfgres_info['qx2_gf_timedelta'] = qx2_gf_timedelta

    metadata_fpath = join(figdir, 'result_metadata.shelf')
    metadata = experiment_storage.ResultMetadata(metadata_fpath)
    #metadata.rrr()
    metadata.connect()
    metadata.sync_test_results(test_result)
    #cfgstr = qreq_.get_cfgstr()
    #cfg_metadata = ensure_item(metadata, cfgstr, {})
    #avuuids = ibs.get_annot_visual_uuids(qaids)
    #avuuid2_ax = ensure_item(cfg_metadata, 'avuuid2_ax', {})
    #cfg_columns = ensure_item(cfg_metadata, 'columns', {})
    #import guitool

    ut.argv_flag_dec(draw_rank_cdf)(ibs, test_result)

    VIZ_INDIVIDUAL_RESULTS = True
    if VIZ_INDIVIDUAL_RESULTS:
        draw_individual_cases(ibs, test_result, metadata=metadata)

    metadata.write()
    #ut.embed()
    #if ut.is_developer():
    if ut.get_argflag(('--guiview', '--gv')):
        import guitool
        guitool.ensure_qapp()
        #wgt = make_test_result_custom_api(ibs, test_result)
        wgt = make_metadata_custom_api(metadata)
        wgt.show()
        wgt.raise_()
        guitool.qtapp_loop(wgt, frequency=100)
    #ut.embed()
    metadata.close()

    if ut.NOT_QUIET:
        print('[DRAW_RESULT] EXIT EXPERIMENT HARNESS')


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.experiments.experiment_drawing
        python -m ibeis.experiments.experiment_drawing --allexamples
        python -m ibeis.experiments.experiment_drawing --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
