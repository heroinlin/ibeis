# -*- coding: utf-8 -*-
"""
Hotspotter pipeline module

Module Notation and Concepts::
    PREFIXES:
    qaid2_XXX - prefix mapping query chip index to
    qfx2_XXX  - prefix mapping query chip feature index to

     * nns    - a (qfx2_idx, qfx2_dist) tuple

     * idx    - the index into the nnindexers descriptors
     * qfx    - query feature index wrt the query chip
     * dfx    - query feature index wrt the database chip
     * dist   - the distance to a corresponding feature
     * fm     - a list of feature match pairs / correspondences (qfx, dfx)
     * fsv    - a score vector of a corresponding feature
     * valid  - a valid bit for a corresponding feature

    PIPELINE_VARS::
    nns_list - maping from query chip index to nns
     * qfx2_idx   - ranked list of query feature indexes to database feature indexes
     * qfx2_dist - ranked list of query feature indexes to database feature indexes

    * qaid2_norm_weight - mapping from qaid to (qfx2_normweight, qfx2_selnorm)
             = qaid2_nnfiltagg[qaid]

CommandLine:
    To see the ouput of a complete pipeline run use

    # Set to whichever database you like
    python main.py --db PZ_MTEST --setdb
    python main.py --db NAUT_test --setdb
    python main.py --db testdb1 --setdb

    # Then run whichever configuration you like
    python main.py --query 1 --yes --noqcache -t default:codename=vsone
    python main.py --query 1 --yes --noqcache -t default:codename=vsone_norm
    python main.py --query 1 --yes --noqcache -t default:codename=vsmany
    python main.py --query 1 --yes --noqcache -t default:codename=vsmany_nsum

TODO:
    * Don't preload the nn-indexer in case the nearest neighbors have already
    been computed?
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from six.moves import zip, range, map
import numpy as np
import vtool as vt
from ibeis.algo.hots import hstypes
from ibeis.algo.hots import chip_match
from ibeis.algo.hots import nn_weights
from ibeis.algo.hots import scoring
from ibeis.algo.hots import _pipeline_helpers as plh  # NOQA
from collections import namedtuple
import utool as ut
print, rrr, profile = ut.inject2(__name__, '[pipeline]')


#=================
# Globals
#=================

TAU = 2 * np.pi  # References: tauday.com
NOT_QUIET = ut.NOT_QUIET and not ut.get_argflag('--quiet-query')
DEBUG_PIPELINE = ut.get_argflag(('--debug-pipeline', '--debug-pipe'))
VERB_PIPELINE =  NOT_QUIET and (ut.VERBOSE or ut.get_argflag(('--verbose-pipeline', '--verb-pipe')))
VERYVERBOSE_PIPELINE = ut.get_argflag(('--very-verbose-pipeline', '--very-verb-pipe'))

USE_HOTSPOTTER_CACHE = not ut.get_argflag('--nocache-hs') and ut.USE_CACHE
USE_NN_MID_CACHE = (
    (True and ut.is_developer()) and
    not ut.get_argflag('--nocache-nnmid') and
    USE_HOTSPOTTER_CACHE
)


NN_LBL      = 'Assign NN:       '
FILT_LBL    = 'Filter NN:       '
WEIGHT_LBL  = 'Weight NN:       '
BUILDCM_LBL = 'Build Chipmatch: '
SVER_LVL    = 'SVER:            '

PROGKW = dict(freq=1, time_thresh=30.0, adjust=True)


# Internal tuples denoting return types
WeightRet_ = namedtuple('weight_ret', ('filtkey_list', 'filtweights_list',
                                       'filtvalids_list', 'filtnormks_list'))
ValidMatchTup_ = namedtuple('vmt', (  # valid_match_tup
    'daid', 'qfx', 'dfx', 'scorevec', 'rank', 'norm_aids', 'norm_fxs'))


class Neighbors(ut.NiceRepr):
    # TODO: replace with named tuple?
    def __init__(self, qaid, idxs, dists, qfxs):
        self.qaid = qaid
        self.qfx_list = qfxs
        self.neighb_idxs = idxs
        self.neighb_dists = dists

    @property
    def num_query_feats(self):
        if self.qfx_list is None:
            return len(self.neighb_idxs)
        else:
            return len(self.qfx_list)

    def __iter__(self):
        return iter([self.neighb_idxs, self.neighb_dists])

    def __getitem__(self, index):
        return (self.neighb_idxs, self.neighb_dists)[index]

    def __nice__(self):
        return '(qaid=%r,nQfxs=%r,nNbs=%r)' % (
            self.qaid, self.num_query_feats, self.neighb_idxs.size)

    def __getstate__(self):
        return self.__dict__

    def __setstate__(self, state):
        return self.__dict__.update(**state)


@profile
def request_ibeis_query_L0(ibs, qreq_, verbose=VERB_PIPELINE):
    r""" Driver logic of query pipeline

    Note:
        Make sure _pipeline_helpres.testrun_pipeline_upto reflects what happens
        in this function.

    Args:
        ibs (ibeis.IBEISController): IBEIS database object to be queried.
            technically this object already lives inside of qreq_.
        qreq_ (ibeis.QueryRequest): hyper-parameters. use
            ``ibs.new_query_request`` to create one

    Returns:
        list: cm_list containing ``ibeis.ChipMatch`` objects

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --show
        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:1 --show

        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db testdb1 --qaid 325
        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db testdb3 --qaid 325
        # background match
        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db NNP_Master3 --qaid 12838

        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0
        python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db PZ_MTEST -a timectrl:qindex=0:256
        python    -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db PZ_Master1 -a timectrl:qindex=0:256
        utprof.py -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --db PZ_Master1 -a timectrl:qindex=0:256

    Example1:
        >>> # ENABLE_DOCTEST
        >>> # one-vs-many:
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> qreq_ = ibeis.init.main_helpers.testdata_qreq_(a=['default:qindex=0:2,dindex=0:10'])
        >>> ibs = qreq_.ibs
        >>> print(qreq_.qparams.query_cfgstr)
        >>> verbose = True
        >>> cm_list = request_ibeis_query_L0(ibs, qreq_, verbose=verbose)
        >>> cm = cm_list[0]
        >>> ut.quit_if_noshow()
        >>> cm.ishow_analysis(qreq_, fnum=0, make_figtitle=True)
        >>> ut.show_if_requested()

    Example2:
        >>> # ENABLE_DOCTEST
        >>> # one-vs-one:
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis  # NOQA
        >>> cfgdict1 = dict(codename='vsone', sv_on=False)
        >>> p = 'default' + ut.get_cfg_lbl(cfgdict1)
        >>> qreq_1 = ibeis.testdata_qreq_(defaultdb='testdb1', p=[p])
        >>> ibs1 = qreq_1.ibs
        >>> print(qreq_1.qparams.query_cfgstr)
        >>> cm_list1 = request_ibeis_query_L0(ibs1, qreq_1)
        >>> cm1 = cm_list1[0]
        >>> ut.quit_if_noshow()
        >>> cm1.ishow_analysis(qreq_1, fnum=1, make_figtitle=True)
        >>> ut.show_if_requested()

    """
    # Load data for nearest neighbors
    if verbose:
        assert ibs is qreq_.ibs
        print('\n\n[hs] +--- STARTING HOTSPOTTER PIPELINE ---')
        print(ut.indent(qreq_.get_infostr(), '[hs] '))

    ibs.assert_valid_aids(qreq_.get_internal_qaids(), msg='pipeline qaids')
    ibs.assert_valid_aids(qreq_.get_internal_daids(), msg='pipeline daids')

    if qreq_.qparams.pipeline_root == 'smk':
        from ibeis.algo.hots.smk import smk_match
        # Alternative to naive bayes matching:
        # Selective match kernel
        qaid2_scores, qaid2_chipmatch_FILT_ = smk_match.execute_smk_L5(qreq_)
    elif qreq_.qparams.pipeline_root in ['vsone', 'vsmany']:
        if qreq_.prog_hook is not None:
            qreq_.prog_hook.initialize_subhooks(5)

        #qreq_.lazy_load(verbose=(verbose and ut.NOT_QUIET))
        qreq_.lazy_preload(verbose=(verbose and ut.NOT_QUIET))
        impossible_daids_list, Kpad_list = build_impossible_daids_list(qreq_)

        # Nearest neighbors (nns_list)
        # a nns object is a tuple(ndarray, ndarray) - (qfx2_dx, qfx2_dist)
        # * query descriptors assigned to database descriptors
        # * FLANN used here
        nns_list = nearest_neighbors(qreq_, Kpad_list, verbose=verbose)

        # Remove Impossible Votes
        # a nnfilt object is an ndarray qfx2_valid
        # * marks matches to the same image as invalid
        nnvalid0_list = baseline_neighbor_filter(qreq_, nns_list,
                                                 impossible_daids_list,
                                                 verbose=verbose)

        # Nearest neighbors weighting / scoring (filtweights_list)
        # filtweights_list maps qaid to filtweights which is a dict
        # that maps a filter name to that query's weights for that filter
        weight_ret = weight_neighbors(qreq_, nns_list, nnvalid0_list,
                                      verbose=verbose)
        filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = weight_ret

        # Nearest neighbors to chip matches (cm_list)
        # * Initial scoring occurs
        # * vsone un-swapping occurs here
        cm_list_FILT = build_chipmatches(qreq_, nns_list, nnvalid0_list,
                                         filtkey_list, filtweights_list, filtvalids_list,
                                         filtnormks_list, verbose=verbose)
    else:
        print('invalid pipeline root %r' % (qreq_.qparams.pipeline_root))

    # Spatial verification (cm_list) (TODO: cython)
    # * prunes chip results and feature matches
    # TODO: allow for reweighting of feature matches to happen.
    cm_list_SVER = spatial_verification(qreq_, cm_list_FILT,
                                        verbose=verbose)
    if cm_list_FILT[0].filtnorm_aids is not None:
        assert cm_list_SVER[0].filtnorm_aids is not None

    # We might just put this check inside the function like it is for SVER.
    # or just not do that and use some good pipeline framework
    if qreq_.qparams.rrvsone_on:
        # VSONE RERANKING
        cm_list = vsone_reranking(qreq_, cm_list_SVER, verbose=verbose)
    else:
        cm_list = cm_list_SVER
        # Final Scoring
        score_method = qreq_.qparams.score_method
        # TODO: move scoring part to pipeline
        scoring.score_chipmatch_list(qreq_, cm_list, score_method)
        # Normalize scores if requested
        if qreq_.qparams.score_normalization:
            normalizer = qreq_.normalizer
            for cm in cm_list:
                # cm.prob_list = normalizer.normalize_score_list(cm.score_list)
                cm.score_list = normalizer.normalize_score_list(cm.score_list)
                # TODO: DO EITHER ANNOT_SCORE_LIST OR NAME_SCORE_LIST
                cm.annot_score_list = normalizer.normalize_score_list(cm.annot_score_list)
                cm.name_score_list = normalizer.normalize_score_list(cm.name_score_list)

    # <HACK>
    # FOR VSMANY DISTINCTIVENSS
    if qreq_.qparams.return_expanded_nns:
        assert qreq_.qparams.vsmany, ' must be in a special vsmany mode'
        # MAJOR HACK TO RETURN ALL QUERY NEAREST NEIGHBORS
        # BREAKS PIPELINE CACHING ASSUMPTIONS
        # SHOULD ONLY BE CALLED BY SPECIAL_QUERY
        # CAUSES TOO MUCH DATA TO BE SAVED
        for cm, nns in zip(cm_list, nns_list):
            cm.qfx2_dist = nns[1]
    # </HACK>

    if VERB_PIPELINE:
        print('[hs] L___ FINISHED HOTSPOTTER PIPELINE ___')

    return cm_list

#============================
# 0) Nearest Neighbors
#============================


def build_impossible_daids_list(qreq_, verbose=VERB_PIPELINE):
    r"""
    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-build_impossible_daids_list

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> # build test data
        >>> qreq_ = ibeis.testdata_qreq_(
        >>>     defaultdb='testdb1',
        >>>     a='default:species=zebra_plains',
        >>>     p='default:use_k_padding=True,can_match_sameimg=False,can_match_samename=False')
        >>> # execute function
        >>> impossible_daids_list, Kpad_list = build_impossible_daids_list(qreq_)
        >>> impossible_daids_list = [x.tolist() for x in impossible_daids_list]
        >>> result = ut.repr2(ut.dict_subset(locals(), ['impossible_daids_list', 'Kpad_list']), nl=1, explicit=True, nobr=True, strvals=True)
        >>> print(result)
        impossible_daids_list=[[1], [4], [5, 6], [5, 6]],
        Kpad_list=[1, 1, 2, 2],
    """
    if verbose:
        print('[hs] Step 0) Build impossible matches')

    can_match_sameimg  = qreq_.qparams.can_match_sameimg
    can_match_samename = qreq_.qparams.can_match_samename
    use_k_padding       = qreq_.qparams.use_k_padding
    cant_match_self     = True
    internal_qaids = qreq_.get_internal_qaids()
    internal_daids = qreq_.get_internal_daids()
    internal_data_nids  = qreq_.get_qreq_annot_nids(internal_daids)

    _impossible_daid_lists = []
    if cant_match_self:
        if can_match_sameimg and can_match_samename:
            # we can skip this if sameimg or samename is specified.
            # it will cover this case for us
            _impossible_daid_lists.append([[qaid] for qaid in internal_qaids])
    if not can_match_sameimg:
        # slow way of getting contact_aids (now incorporates faster way)
        contact_aids_list = qreq_.ibs.get_annot_contact_aids(internal_qaids,
                                                             daid_list=internal_daids)
        _impossible_daid_lists.append(contact_aids_list)
        EXTEND_TO_OTHER_CONTACT_GT = False
        # TODO: flag overlapping keypoints with another annot as likely to
        # cause photobombs.
        # Also cannot match any aids with a name of an annotation in this image
        if EXTEND_TO_OTHER_CONTACT_GT:
            # TODO: need a test set that can accomidate testing this case
            # testdb1 might cut it if we spruced it up
            nonself_contact_aids = [
                np.setdiff1d(aids, qaid)
                for aids, qaid in zip(contact_aids_list, internal_qaids)]
            nonself_contact_nids = qreq_.ibs.unflat_map(
                qreq_.get_qreq_annot_nids, nonself_contact_aids)
            contact_aids_gt_list = [
                internal_daids.compress(
                    vt.get_covered_mask(internal_data_nids, nids))
                for nids in nonself_contact_nids
            ]
            _impossible_daid_lists.append(contact_aids_gt_list)

    if not can_match_samename:
        internal_data_nids  = qreq_.get_qreq_annot_nids(internal_daids)
        internal_query_nids = qreq_.get_qreq_annot_nids(internal_qaids)
        gt_aids = [
            internal_daids.compress(internal_data_nids == nid)
            for nid in internal_query_nids
        ]
        _impossible_daid_lists.append(gt_aids)
    # TODO: add explicit not a match case in here
    _impossible_daids_list = list(map(ut.flatten, zip(*_impossible_daid_lists)))
    impossible_daids_list = [
        np.unique(impossible_daids)
        for impossible_daids in _impossible_daids_list]

    # TODO: we need to pad K for each bad annotation
    if qreq_.qparams.vsone:
        # dont pad vsone
        Kpad_list = [0 for _ in range(len(impossible_daids_list))]
    else:
        if use_k_padding:
            Kpad_list = list(map(len, impossible_daids_list))  # NOQA
        else:
            # always at least pad K for self queries
            Kpad_list =  [
                1 if qaid in internal_daids else 0 for qaid in internal_qaids]
    return impossible_daids_list, Kpad_list

#============================
# 1) Nearest Neighbors
#============================


@profile
def nearest_neighbor_cacheid2(qreq_, Kpad_list):
    r"""
    Returns a hacky cacheid for neighbor configs.
    DEPRICATE: This will be replaced by dtool caching

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        Kpad_list (list):

    Returns:
        tuple: (nn_mid_cacheid_list, nn_cachedir)

    CommandLine:
        python -m ibeis.algo.hots.pipeline --exec-nearest_neighbor_cacheid2
        python -m ibeis.algo.hots.pipeline --exec-nearest_neighbor_cacheid2 --superstrict

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> verbose = True
        >>> cfgdict = dict(K=4, Knorm=1, use_k_padding=False)
        >>> # test 1
        >>> p = 'default' + ut.get_cfg_lbl(cfgdict)
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='testdb1', p=[p], qaid_override=[1, 2], daid_override=[1, 2, 3, 4, 5])
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'nearest_neighbors')
        >>> Kpad_list, = ut.dict_take(locals_, ['Kpad_list'])
        >>> tup = nearest_neighbor_cacheid2(qreq_, Kpad_list)
        >>> (nn_cachedir, nn_mid_cacheid_list) = tup
        >>> result1 = 'nn_mid_cacheid_list1 = ' + ut.list_str(nn_mid_cacheid_list)
        >>> # test 2
        >>> cfgdict2 = dict(K=2, Knorm=3, use_k_padding=True)
        >>> p2 = 'default' + ut.get_cfg_lbl(cfgdict)
        >>> ibs = qreq_.ibs
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='testdb1', p=[p2], qaid_override=[1, 2], daid_override=[1, 2, 3, 4, 5])
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'nearest_neighbors')
        >>> Kpad_list, = ut.dict_take(locals_, ['Kpad_list'])
        >>> tup = nearest_neighbor_cacheid2(qreq_, Kpad_list)
        >>> (nn_cachedir, nn_mid_cacheid_list) = tup
        >>> result2 = 'nn_mid_cacheid_list2 = ' + ut.list_str(nn_mid_cacheid_list)
        >>> result = result1 + '\n' + result2
        >>> print(result)
        nn_mid_cacheid_list1 = [
            'nnobj_8687dcb6-1f1f-fdd3-8b72-8f36f9f41905_DVUUIDS((5)oavtblnlrtocnrpm)_NN(single,cks800)_Chip(sz700,width)_Feat(hesaff+sift)_FLANN(8_kdtrees)_truek6',
            'nnobj_a2aef668-20c1-1897-d8f3-09a47a73f26a_DVUUIDS((5)oavtblnlrtocnrpm)_NN(single,cks800)_Chip(sz700,width)_Feat(hesaff+sift)_FLANN(8_kdtrees)_truek6',
        ]
        nn_mid_cacheid_list2 = [
            'nnobj_8687dcb6-1f1f-fdd3-8b72-8f36f9f41905_DVUUIDS((5)oavtblnlrtocnrpm)_NN(single,cks800)_Chip(sz700,width)_Feat(hesaff+sift)_FLANN(8_kdtrees)_truek6',
            'nnobj_a2aef668-20c1-1897-d8f3-09a47a73f26a_DVUUIDS((5)oavtblnlrtocnrpm)_NN(single,cks800)_Chip(sz700,width)_Feat(hesaff+sift)_FLANN(8_kdtrees)_truek6',
        ]

    """
    from ibeis.algo import Config
    internal_daids = qreq_.get_internal_daids()
    internal_qaids = qreq_.get_internal_qaids()
    data_hashid = qreq_.ibs.get_annot_hashid_visual_uuid(
        internal_daids, prefix='D')

    HACK_KCFG = not ut.SUPER_STRICT

    if HACK_KCFG:
        # hack config so we consolidate different k values
        # (ie, K=2,Knorm=1 == K=1,Knorm=2)
        nn_cfgstr = Config.NNConfig(**qreq_.qparams).get_cfgstr(
            ignore_keys={'K', 'Knorm', 'use_k_padding'})
    else:
        nn_cfgstr      = qreq_.qparams.nn_cfgstr

    chip_cfgstr    = qreq_.qparams.chip_cfgstr
    feat_cfgstr    = qreq_.qparams.feat_cfgstr
    flann_cfgstr   = qreq_.qparams.flann_cfgstr
    single_name_condition   = qreq_.qparams.single_name_condition
    assert single_name_condition is False, 'can not be on yet'
    aug_cfgstr = ('aug_quryside' if qreq_.qparams.augment_queryside_hack
                  else '')
    nn_mid_cacheid = ''.join([data_hashid, nn_cfgstr, chip_cfgstr, feat_cfgstr,
                              flann_cfgstr, aug_cfgstr])
    print('nn_mid_cacheid = %r' % (nn_mid_cacheid,))

    if single_name_condition:
        query_hashid_list = qreq_.ibs.get_annot_semantic_uuids(internal_qaids)
    else:
        query_hashid_list = qreq_.ibs.get_annot_visual_uuids(internal_qaids)

    if HACK_KCFG:
        kbase = qreq_.qparams.K + int(qreq_.qparams.Knorm)
        nn_mid_cacheid_list = [
            'nnobj_' + str(query_hashid) + nn_mid_cacheid + '_truek' + str(kbase + Kpad)
            for query_hashid, Kpad in zip(query_hashid_list, Kpad_list)]
    else:
        nn_mid_cacheid_list = [
            'nnobj_' + str(query_hashid) + nn_mid_cacheid + '_' + str(Kpad)
            for query_hashid, Kpad in zip(query_hashid_list, Kpad_list)]

    nn_cachedir = qreq_.ibs.get_neighbor_cachedir()
    # ut.unixjoin(qreq_.ibs.get_cachedir(), 'neighborcache2')
    ut.ensuredir(nn_cachedir)
    if ut.VERBOSE:
        print('nn_mid_cacheid = %r' % (nn_mid_cacheid,))
        pass
    return nn_cachedir, nn_mid_cacheid_list


@profile
def cachemiss_nn_compute_fn(flags_list, qreq_, Kpad_list, K, Knorm, single_name_condition, verbose):
    """
    Logic for computing neighbors if there is a cache miss

    >>> flags_list = [True] * len(Kpad_list)
    >>> flags_list = [True, False, True]
    """
    # Cant do this here because of get_nn_aids. bleh
    # Could make this slightly more efficient
    #qreq_.load_indexer(verbose=verbose)

    #internal_qaids = qreq_.get_internal_qaids()
    #internal_qaids = internal_qaids.compress(flags_list)

    # Get only the data that needs to be computed
    internal_qannots = qreq_.internal_qannots
    internal_qannots = internal_qannots.compress(flags_list)

    Kpad_list = ut.compress(Kpad_list, flags_list)
    # do computation
    num_neighbors_list = [K + Kpad + Knorm for Kpad in Kpad_list]
    config2_ = qreq_.get_internal_query_config2()
    #qvecs_list = qreq_.ibs.get_annot_vecs(
    #    internal_qaids, config2_=config2_)
    qvecs_list = internal_qannots.vecs
    #ibs.get_annot_vecs(internal_qaids, config2_=config2_)

    qfxs_list = [np.arange(len(qvecs)) for qvecs in qvecs_list]

    if config2_.minscale_thresh is not None or config2_.maxscale_thresh is not None:
        min_ = -np.inf if config2_.minscale_thresh is None else config2_.minscale_thresh
        max_ = np.inf if config2_.maxscale_thresh is None else config2_.maxscale_thresh
        #qkpts_list = qreq_.ibs.get_annot_kpts(internal_qaids, config2_=config2_)
        qkpts_list = internal_qannots.kpts
        qkpts_list = vt.ziptake(qkpts_list, qfxs_list, axis=0)
        # kpts_list = vt.ziptake(kpts_list, fxs_list, axis=0)  # not needed for first filter
        scales_list = [vt.get_scales(kpts) for kpts in qkpts_list]
        # Remove data under the threshold
        flags_list = [np.logical_and(scales >= min_, scales <= max_) for scales in scales_list]
        qvecs_list = vt.zipcompress(qvecs_list, flags_list, axis=0)
        qfxs_list = vt.zipcompress(qfxs_list, flags_list, axis=0)

    if config2_.fgw_thresh is not None:
        #qfgw_list = qreq_.ibs.get_annot_fgweights(
        #    internal_qaids, config2_=config2_)
        qfgw_list = internal_qannots.fgweights
        qfgw_list = vt.ziptake(qfgw_list, qfxs_list, axis=0)
        fgw_thresh = config2_.fgw_thresh
        flags_list = [fgws >= fgw_thresh for fgws in qfgw_list]
        qfxs_list = vt.zipcompress(qfxs_list, flags_list, axis=0)
        qvecs_list = vt.zipcompress(qvecs_list, flags_list, axis=0)

    if verbose:
        if len(qvecs_list) == 1:
            print('[hs] depth(qvecs_list) = %r' %
                  (ut.depth_profile(qvecs_list),))
    # Mark progress ane execute nearest indexer nearest neighbor code
    prog_hook = (None if qreq_.prog_hook is None else
                 qreq_.prog_hook.next_subhook())
    qvec_iter = ut.ProgressIter(qvecs_list, lbl=NN_LBL,
                                prog_hook=prog_hook, **PROGKW)
    if single_name_condition:
        pass
    else:
        idx_dist_list = [
            qreq_.indexer.knn(qfx2_vec, num_neighbors)
            for qfx2_vec, num_neighbors in zip(qvec_iter, num_neighbors_list)]

    # Move into new object structure
    nns_list = [Neighbors(qaid, idxs, dists, qfxs)
                for qaid, qfxs, (idxs, dists) in zip(internal_qannots.aid, qfxs_list, idx_dist_list)]

    return nns_list


@profile
def nearest_neighbors(qreq_, Kpad_list, verbose=VERB_PIPELINE):
    """
    Plain Nearest Neighbors
    Tries to load nearest neighbors from a cache instead of recomputing them.

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-nearest_neighbors
        python -m ibeis.algo.hots.pipeline --test-nearest_neighbors --db PZ_MTEST --qaids=1:100
        utprof.py -m ibeis.algo.hots.pipeline --test-nearest_neighbors --db PZ_MTEST --qaids=1:100

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> verbose = True
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='testdb1', qaid_override=[1, 2, 3])
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'nearest_neighbors')
        >>> Kpad_list, = ut.dict_take(locals_, ['Kpad_list'])
        >>> # execute function
        >>> nns_list = nearest_neighbors(qreq_, Kpad_list, verbose=verbose)
        >>> qaid = qreq_.internal_qaids[0]
        >>> nn = nns_list[0]
        >>> (qfx2_idx, qfx2_dist) = nn
        >>> num_neighbors = Kpad_list[0] + qreq_.qparams.K + qreq_.qparams.Knorm
        >>> # Assert nns tuple is valid
        >>> ut.assert_eq(qfx2_idx.shape, qfx2_dist.shape)
        >>> ut.assert_eq(qfx2_idx.shape[1], num_neighbors)
        >>> ut.assert_inbounds(qfx2_idx.shape[0], 1000, 3000)
    """
    K      = qreq_.qparams.K
    Knorm  = qreq_.qparams.Knorm
    single_name_condition = qreq_.qparams.single_name_condition
    #checks = qreq_.qparams.checks
    # Get both match neighbors (including padding) and normalizing neighbors
    if verbose:
        print('[hs] Step 1) Assign nearest neighbors: %s' %
              (qreq_.qparams.nn_cfgstr,))

    prog_hook = (None if qreq_.prog_hook is None else
                 qreq_.prog_hook.next_subhook())
    qreq_.load_indexer(verbose=verbose, prog_hook=prog_hook)
    # For each internal query annotation
    # Find the nearest neighbors of each descriptor vector
    #USE_NN_MID_CACHE = ut.is_developer()
    nn_cachedir, nn_mid_cacheid_list = nearest_neighbor_cacheid2(
        qreq_, Kpad_list)

    use_cache = USE_NN_MID_CACHE
    nns_list = ut.tryload_cache_list_with_compute(
        use_cache, nn_cachedir, 'neighbs4', nn_mid_cacheid_list,
        cachemiss_nn_compute_fn, qreq_, Kpad_list, K, Knorm, single_name_condition, verbose)
    return nns_list


#============================
# 2) Remove Impossible Weights
#============================


@profile
def baseline_neighbor_filter(qreq_, nns_list, impossible_daids_list, verbose=VERB_PIPELINE):
    """
    Removes matches to self, the same image, or the same name.

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-baseline_neighbor_filter

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *   # NOQA
        >>> import ibeis
        >>> qreq_, nns_list, impossible_daids_list = plh.testdata_pre_baselinefilter(qaid_list=[1, 2, 3, 4], codename='vsmany')
        >>> nnvalid0_list = baseline_neighbor_filter(qreq_, nns_list, impossible_daids_list)
        >>> ut.assert_eq(len(nnvalid0_list), len(qreq_.qaids))
        >>> #ut.assert_eq(nnvalid0_list[0].shape[1], qreq_.qparams.K, 'does not match k')
        >>> #ut.assert_eq(qreq_.qparams.K, 4, 'k is not 4')
        >>> assert not np.any(nnvalid0_list[0][:, 0]), (
        ...    'first col should be all invalid because of self match')
        >>> assert not np.all(nnvalid0_list[0][:, 1]), (
        ...    'second col should have some good matches')
        >>> ut.assert_inbounds(nnvalid0_list[0].sum(), 1000, 10000)

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *   # NOQA
        >>> import ibeis
        >>> qreq_, nns_list, impossible_daids_list = plh.testdata_pre_baselinefilter(codename='vsone')
        >>> nnvalid0_list = baseline_neighbor_filter(qreq_, nns_list, impossible_daids_list)
        >>> ut.assert_eq(len(nnvalid0_list), len(qreq_.daids))
        >>> ut.assert_eq(qreq_.qparams.K, 1, 'k is not 1')
        >>> ut.assert_eq(nnvalid0_list[0].shape[1], qreq_.qparams.K, 'does not match k')
        >>> ut.assert_eq(nnvalid0_list[0].sum(), 0, 'no self matches')
        >>> ut.assert_inbounds(nnvalid0_list[1].sum(), 200, 1500)
    """
    if verbose:
        print('[hs] Step 2) Baseline neighbor filter')
    Knorm = qreq_.qparams.Knorm
    # Find which annotations each query matched against
    neighb_aids_iter = (qreq_.indexer.get_nn_aids(nn.neighb_idxs.T[0:-Knorm].T)
                        for nn in nns_list)
    filter_iter_ = zip(neighb_aids_iter, impossible_daids_list)
    prog_hook = None if qreq_.prog_hook is None else qreq_.prog_hook.next_subhook()
    filter_iter = ut.ProgressIter(filter_iter_, nTotal=len(nns_list),
                                  lbl=FILT_LBL, prog_hook=prog_hook, **PROGKW)
    # Check to be sure that none of the matched annotations are in the impossible set
    nnvalid0_list = [
        vt.get_uncovered_mask(neighb_aids, impossible_daids)
        for neighb_aids, impossible_daids in filter_iter
    ]
    return nnvalid0_list


#============================
# 3) Nearest Neighbor weights
#============================


@profile
def weight_neighbors(qreq_, nns_list, nnvalid0_list, verbose=VERB_PIPELINE):
    """
    pipeline step 3 -
    assigns weights to feature matches based on the active filter list

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-weight_neighbors
        python -m ibeis.algo.hots.pipeline --test-weight_neighbors:0 --verbose --verbtd --ainfo --nocache --veryverbose
        python -m ibeis.algo.hots.pipeline --test-weight_neighbors:0 --show
        python -m ibeis.algo.hots.pipeline --test-weight_neighbors:1 --show

        python -m ibeis.algo.hots.pipeline --test-weight_neighbors:0 --show -t default:lnbnn_normer=lnbnn_fg_0.9__featscore,lnbnn_norm_thresh=.9

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('weight_neighbors', defaultdb='testdb1',
        >>>                                a=['default:qindex=0:3,dindex=0:5,hackerrors=False'],
        >>>                                p=['default:codename=vsmany,bar_l2_on=True,fg_on=False'], verbose=True)
        >>> nns_list, nnvalid0_list = args
        >>> verbose = True
        >>> # execute function
        >>> weight_ret = weight_neighbors(qreq_, nns_list, nnvalid0_list, verbose)
        >>> filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = weight_ret
        >>> import plottool as pt
        >>> verbose = True
        >>> cm_list = build_chipmatches(
        >>>     qreq_, nns_list, nnvalid0_list, filtkey_list, filtweights_list,
        >>>     filtvalids_list, filtnormks_list, verbose=verbose)
        >>> ut.quit_if_noshow()
        >>> cm = cm_list[0]
        >>> cm.score_nsum(qreq_)
        >>> cm.ishow_analysis(qreq_)
        >>> ut.show_if_requested()

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('weight_neighbors', defaultdb='testdb1',
        >>>                                a=['default:qindex=0:3,dindex=0:5,hackerrors=False'],
        >>>                                p=['default:codename=vsmany,bar_l2_on=True,fg_on=False'], verbose=True)
        >>> nns_list, nnvalid0_list = args
        >>> verbose = True
        >>> # execute function
        >>> weight_ret = weight_neighbors(qreq_, nns_list, nnvalid0_list, verbose)
        >>> filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = weight_ret
        >>> nInternAids = len(qreq_.get_internal_qaids())
        >>> nFiltKeys = len(filtkey_list)
        >>> filtweight_depth = ut.depth_profile(filtweights_list)
        >>> filtvalid_depth = ut.depth_profile(filtvalids_list)
        >>> ut.assert_eq(nInternAids, len(filtweights_list))
        >>> ut.assert_eq(nInternAids, len(filtvalids_list))
        >>> ut.assert_eq(ut.get_list_column(filtweight_depth, 0), [nFiltKeys] * nInternAids)
        >>> ut.assert_eq(filtvalid_depth, (nInternAids, nFiltKeys))
        >>> ut.assert_eq(filtvalids_list, [[None, None], [None, None], [None, None]])
        >>> ut.assert_eq(filtkey_list, [hstypes.FiltKeys.LNBNN, hstypes.FiltKeys.BARL2])
        >>> ut.quit_if_noshow()
        >>> import plottool as pt
        >>> verbose = True
        >>> cm_list = build_chipmatches(
        >>>     qreq_, nns_list, nnvalid0_list, filtkey_list, filtweights_list,
        >>>     filtvalids_list, filtnormks_list, verbose=verbose)
        >>> cm = cm_list[0]
        >>> cm.score_nsum(qreq_)
        >>> cm.ishow_analysis(qreq_)
        >>> ut.show_if_requested()

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('weight_neighbors', defaultdb='testdb1',
        >>>                                a=['default:qindex=0:1,dindex=0:5,hackerrors=False'],
        >>>                                p=['default:codename=vsone,fg_on=False,ratio_thresh=.625'], verbose=True)
        >>> nns_list, nnvalid0_list = args
        >>> weight_ret = weight_neighbors(qreq_, nns_list, nnvalid0_list)
        >>> filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = weight_ret
        >>> nFiltKeys = len(filtkey_list)
        >>> nInternAids = len(qreq_.get_internal_qaids())
        >>> filtweight_depth = ut.depth_profile(filtweights_list)
        >>> filtvalid_depth = ut.depth_profile(filtvalids_list)
        >>> ut.assert_eq(nInternAids, len(filtweights_list))
        >>> ut.assert_eq(nInternAids, len(filtvalids_list))
        >>> target = [nFiltKeys] * nInternAids
        >>> ut.assert_eq(ut.get_list_column(filtweight_depth, 0), target)
        >>> ut.assert_eq(filtkey_list, [hstypes.FiltKeys.RATIO])
        >>> assert filtvalids_list[0][0] is not None
        >>> ut.quit_if_noshow()
        >>> import plottool as pt
        >>> verbose = True
        >>> cm_list = build_chipmatches(
        >>>     qreq_, nns_list, nnvalid0_list, filtkey_list, filtweights_list,
        >>>     filtvalids_list, filtnormks_list, verbose=verbose)
        >>> cm = cm_list[0]
        >>> cm.score_nsum(qreq_)
        >>> cm.ishow_analysis(qreq_)
        >>> ut.show_if_requested()
    """
    if verbose:
        print('[hs] Step 3) Weight neighbors: ' + qreq_.qparams.nnweight_cfgstr)
        if len(nns_list) == 1:
            print('[hs] depth(nns_list) ' + str(ut.depth_profile(nns_list)))

    #print(WEIGHT_LBL)
    #intern_qaid_iter = ut.ProgressIter(internal_qaids, lbl=BUILDCM_LBL,
    #                                   **PROGKW)

    # Build weights for each active filter
    filtkey_list     = []
    _filtweight_list = []
    _filtvalid_list  = []
    _filtnormk_list  = []

    config2_ = qreq_.extern_data_config2

    # soft_weights = ['lnbnn', 'normonly', 'bar_l2', 'const', 'borda', 'fg']
    # for filtname in soft_weights:
    #     pass
    # hard_weights = ['ratio']

    if not config2_.sqrd_dist_on:
        # Take the square root of the squared distances
        for nns in nns_list:
            nns.neighb_dists = np.sqrt(nns.neighb_dists.astype(np.float64))
        # nns_list_ = [(neighb_idx, np.sqrt(neighb_dist.astype(np.float64)))
        #              for neighb_idx, neighb_dist in nns_list]
        # nns_list = nns_list_

    if config2_.lnbnn_on:
        filtname = 'lnbnn'
        lnbnn_weight_list, normk_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)

        if config2_.lnbnn_normer is not None:
            print('[hs] normalizing feat scores')
            if qreq_.lnbnn_normer is None:
                qreq_.lnbnn_normer = vt.ScoreNormalizer()
                # qreq_.lnbnn_normer.load(cfgstr=config2_.lnbnn_normer)
                qreq_.lnbnn_normer.fuzzyload(partial_cfgstr=config2_.lnbnn_normer)

            lnbnn_weight_list = [
                qreq_.lnbnn_normer.normalize_scores(s.ravel()).reshape(s.shape)
                for s in lnbnn_weight_list
            ]

            # Thresholding like a champ!
            lnbnn_norm_thresh = config2_.lnbnn_norm_thresh
            # lnbnn_weight_list = [
            #     s * [s > lnbnn_norm_thresh] for s in lnbnn_weight_list
            # ]
            lnbnn_isvalid = [s > lnbnn_norm_thresh for s in lnbnn_weight_list]
            # Softmaxing
            # from scipy.special import expit
            # y = expit(x * 6)
            # lnbnn_weight_list = [
            #     vt.logistic_01(s)
            #     for s in lnbnn_weight_list
            # ]
            filtname += '_norm'
            _filtvalid_list.append(lnbnn_isvalid)  # None means all valid
        else:
            _filtvalid_list.append(None)  # None means all valid

        _filtweight_list.append(lnbnn_weight_list)
        _filtnormk_list.append(normk_list)
        filtkey_list.append(filtname)
    if config2_.normonly_on:
        filtname = 'normonly'
        normonly_weight_list, normk_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        _filtweight_list.append(normonly_weight_list)
        _filtvalid_list.append(None)  # None means all valid
        _filtnormk_list.append(normk_list)
        filtkey_list.append(filtname)
    if config2_.bar_l2_on:
        filtname = 'bar_l2'
        bar_l2_weight_list, normk_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        _filtweight_list.append(bar_l2_weight_list)
        _filtvalid_list.append(None)  # None means all valid
        _filtnormk_list.append(None)
        filtkey_list.append(filtname)
    if config2_.ratio_thresh:
        filtname = 'ratio'
        ratio_weight_list, normk_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        ratio_isvalid   = [neighb_ratio <= qreq_.qparams.ratio_thresh for
                           neighb_ratio in ratio_weight_list]
        # HACK TO GET 1 - RATIO AS SCORE
        ratioscore_list = [np.subtract(1, neighb_ratio)
                           for neighb_ratio in ratio_weight_list]
        _filtweight_list.append(ratioscore_list)
        _filtvalid_list.append(ratio_isvalid)
        _filtnormk_list.append(normk_list)
        filtkey_list.append(filtname)
    # --simple weighted implm
    if config2_.const_on:
        filtname = 'const'
        constvote_weight_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        _filtweight_list.append(constvote_weight_list)
        _filtvalid_list.append(None)  # None means all valid
        _filtnormk_list.append(None)
        filtkey_list.append(filtname)
    if config2_.borda_on:
        filtname = 'borda'
        constvote_weight_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        _filtweight_list.append(constvote_weight_list)
        _filtvalid_list.append(None)  # None means all valid
        _filtnormk_list.append(None)
        filtkey_list.append(filtname)
    if config2_.fg_on:
        filtname = 'fg'
        fgvote_weight_list = nn_weights.NN_WEIGHT_FUNC_DICT[filtname](
            nns_list, nnvalid0_list, qreq_)
        _filtweight_list.append(fgvote_weight_list)
        _filtvalid_list.append(None)  # None means all valid
        _filtnormk_list.append(None)
        filtkey_list.append(filtname)

    # Switch nested list structure from [filt, qaid] to [qaid, filt]
    nInternAids = len(nns_list)
    filtweights_list = [ut.get_list_column(_filtweight_list, index)
                        for index in range(nInternAids)]
    filtvalids_list = [[
        None if filtvalid is None else filtvalid[index]
        for filtvalid in _filtvalid_list
    ] for index in range(nInternAids) ]
    # print('ut.depth_profile(_filtweight_list) = %r' % (ut.depth_profile(_filtweight_list),))
    # print('ut.depth_profile(filtweights_list) = %r' % (ut.depth_profile(filtweights_list),))

    filtnormks_list = [[
        None if normk is None else normk[index]
        for normk in _filtnormk_list
    ] for index in range(nInternAids)]

    assert len(filtkey_list) > 0, (
        'no feature correspondece filter keys were specified')

    weight_ret = WeightRet_(filtkey_list, filtweights_list, filtvalids_list, filtnormks_list)
    return weight_ret


#============================
# 4) Conversion from featurematches to chipmatches neighb -> aid2
#============================


@profile
def build_chipmatches(qreq_, nns_list, nnvalid0_list, filtkey_list,
                      filtweights_list, filtvalids_list, filtnormks_list,
                      verbose=VERB_PIPELINE):
    """
    pipeline step 4 - builds sparse chipmatches

    Takes the dense feature matches from query feature to (what could be any)
    database features and builds sparse matching pairs for each annotation to
    annotation match.

    Ignore:
        python -c "import utool; print(utool.auto_docstr('ibeis.algo.hots.pipeline', 'build_chipmatches'))"

    CommandLine:
        python -m ibeis build_chipmatches
        python -m ibeis build_chipmatches:0 --show
        python -m ibeis build_chipmatches:1 --show
        python -m ibeis build_chipmatches:2 --show

    Example0:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('build_chipmatches', p=['default:codename=vsmany'])
        >>> nns_list, nnvalid0_list, filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = args
        >>> verbose = True
        >>> # execute function
        >>> cm_list = build_chipmatches(qreq_, *args, verbose=verbose)
        >>> # verify results
        >>> [cm.assert_self(qreq_) for cm in cm_list]
        >>> cm = cm_list[0]
        >>> fm = cm.fm_list[cm.daid2_idx[2]]
        >>> num_matches = len(fm)
        >>> print('vsone num_matches = %r' % num_matches)
        >>> ut.assert_inbounds(num_matches, 500, 2000, 'vsmany nmatches out of bounds')
        >>> ut.quit_if_noshow()
        >>> cm.score_csum(qreq_)
        >>> cm_list[0].ishow_single_annotmatch(qreq_)
        >>> ut.show_if_requested()

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> qreq_, args = plh.testdata_pre('build_chipmatches', p=['default:codename=vsone,sqrd_dist_on=True'])
        >>> nns_list, nnvalid0_list, filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = args
        >>> # execute function
        >>> cm_list = build_chipmatches(qreq_, *args, verbose=verbose)
        >>> # verify results
        >>> [cm.assert_self(qreq_) for cm in cm_list]
        >>> cm = cm_list[0]
        >>> fm = cm.fm_list[cm.daid2_idx[2]]
        >>> num_matches = len(fm)
        >>> print('vsone num_matches = %r' % num_matches)
        >>> ut.assert_inbounds(num_matches, 25, 100, 'vsone nmatches out of bounds')
        >>> ut.quit_if_noshow()
        >>> cm.show_single_annotmatch(qreq_, daid=2)
        >>> cm.score_csum(qreq_)
        >>> ut.show_if_requested()

    Example2:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> # Test to make sure filtering by feature weights works
        >>> qreq_, args = plh.testdata_pre('build_chipmatches', p=['default:codename=vsmany,fgw_thresh=.9'])
        >>> nns_list, nnvalid0_list, filtkey_list, filtweights_list, filtvalids_list, filtnormks_list = args
        >>> verbose = True
        >>> # execute function
        >>> cm_list = build_chipmatches(qreq_, *args, verbose=verbose)
        >>> # verify results
        >>> [cm.assert_self(qreq_) for cm in cm_list]
        >>> cm = cm_list[0]
        >>> fm = cm.fm_list[cm.daid2_idx[2]]
        >>> num_matches = len(fm)
        >>> print('vsone num_matches = %r' % num_matches)
        >>> ut.assert_inbounds(num_matches, 100, 300, 'vsmany nmatches out of bounds')
        >>> ut.quit_if_noshow()
        >>> cm.score_csum(qreq_)
        >>> cm_list[0].ishow_single_annotmatch(qreq_)
        >>> ut.show_if_requested()
    """
    is_vsone =  qreq_.qparams.vsone
    Knorm = qreq_.qparams.Knorm
    if verbose:
        pipeline_root = qreq_.qparams.pipeline_root
        print('[hs] Step 4) Building chipmatches %s' % (pipeline_root,))
    idx_list = [nns.neighb_idxs for nns in nns_list]
    #nnvalid0_list
    # if filtnormks_list is None:
    #     filtnormks_list = [None] * len(filtweights_list)
    # for isvalid0, score_list, isvalid1, normks in zip(nnvalid0_list, filtweights_list, filtvalids_list, filtnormks_list):
    #     pass

    vmt_list = [
        get_sparse_matchinfo_nonagg(
            qreq_, nns, neighb_idx, neighb_valid0, neighb_score_list,
            neighb_valid_list, neighb_normk_list, Knorm)
        for nns, neighb_idx, neighb_valid0, neighb_score_list, neighb_valid_list, neighb_normk_list in
        zip(nns_list, idx_list, nnvalid0_list, filtweights_list, filtvalids_list, filtnormks_list)
    ]
    # Iterate over INTERNAL query annotation ids
    internal_qaids = qreq_.get_internal_qaids()
    external_qaids = qreq_.qaids
    external_daids = qreq_.daids
    prog_hook = None if qreq_.prog_hook is None else qreq_.prog_hook.next_subhook()
    intern_qaid_iter = ut.ProgressIter(internal_qaids, lbl=BUILDCM_LBL,
                                       prog_hook=prog_hook, **PROGKW)
    #intern_qaid_iter = internal_qaids

    if is_vsone:
        # VSONE build one cmtup_old
        assert len(external_qaids) == 1, 'vsone can only accept one external qaid'
        assert np.all(external_daids == internal_qaids)
        # build vsone dict output
        qaid = external_qaids[0]
        cm = chip_match.ChipMatch.from_vsone_match_tup(
            vmt_list, daid_list=external_daids, qaid=qaid,
            fsv_col_lbls=filtkey_list)
        cm_list = [cm]
    else:
        # VSMANY build many cmtup_olds
        cm_list = [
            chip_match.ChipMatch.from_vsmany_match_tup(
                vmt, qaid=qaid, fsv_col_lbls=filtkey_list)
            for vmt, qaid in zip(vmt_list, intern_qaid_iter)]
    return cm_list


@profile
def get_sparse_matchinfo_nonagg(qreq_, nns, neighb_idx, neighb_valid0,
                                neighb_score_list, neighb_valid_list,
                                neighb_normk_list, Knorm):
    """
    builds sparse iterator that generates feature match pairs, scores, and ranks

    Returns:
        ValidMatchTup_ : vmt a tuple of corresponding lists. Each item in the
            list corresponds to a daid, dfx, scorevec, rank, norm_aid, norm_fx...

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-get_sparse_matchinfo_nonagg:0 --show
        python -m ibeis.algo.hots.pipeline --test-get_sparse_matchinfo_nonagg:1 --show

        utprof.py -m ibeis.algo.hots.pipeline --test-get_sparse_matchinfo_nonagg

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> qreq_, qaid, daid, args = plh.testdata_sparse_matchinfo_nonagg(p=['default:codename=vsone'])
        >>> nns, neighb_idx, neighb_valid0, neighb_score_list, neighb_valid_list, neighb_normk_list, Knorm = args
        >>> qannot = qreq_.ibs.annots([qaid], qreq_.qparams)
        >>> dannot = qreq_.ibs.annots([daid], qreq_.qparams)
        >>> # execute function
        >>> vmt = get_sparse_matchinfo_nonagg(qreq_, *args)
        >>> # check results
        >>> assert ut.allsame(list(map(len, vmt[:-2]))), 'need same num rows'
        >>> ut.assert_inbounds(vmt.dfx, -1, qannot.num_feats)
        >>> ut.assert_inbounds(vmt.qfx, -1, dannot.num_feats)
        >>> ut.quit_if_noshow()
        >>> daid_list = [daid]
        >>> vmt_list = [vmt]
        >>> cm = chip_match.ChipMatch.from_vsone_match_tup(vmt_list, daid_list=daid_list, qaid=qaid, fsv_col_lbls=['ratio'])
        >>> cm.assert_self(verbose=False)
        >>> ut.quit_if_noshow()
        >>> cm.score_csum(qreq_)
        >>> cm.show_single_annotmatch(qreq_)
        >>> ut.show_if_requested()

    Example0:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> verbose = True
        >>> qreq_, qaid, daid, args = plh.testdata_sparse_matchinfo_nonagg(
        >>>     defaultdb='PZ_MTEST', p=['default:Knorm=3,normalizer_rule=name,const_on=True,ratio_thresh=.2,sqrd_dist_on=True'])
        >>> nns, neighb_idx, neighb_valid0, neighb_score_list, neighb_valid_list, neighb_normk_list, Knorm = args
        >>> # execute function
        >>> vmt = get_sparse_matchinfo_nonagg(qreq_, *args)
        >>> qannot = qreq_.ibs.annots([qaid], qreq_.qparams)
        >>> dannot = qreq_.ibs.annots(vmt.daid, qreq_.qparams)
        >>> # check results
        >>> assert ut.allsame(list(map(len, vmt[:-2]))), 'need same num rows'
        >>> ut.assert_inbounds(vmt.qfx, -1, qannot.num_feats)
        >>> ut.assert_inbounds(vmt.dfx, -1, np.array(dannot.num_feats))
        >>> cm = chip_match.ChipMatch.from_vsmany_match_tup(vmt, qaid=qaid)
        >>> cm.assert_self(verbose=False)
        >>> ut.quit_if_noshow()
        >>> cm.score_csum(qreq_)
        >>> cm.show_single_annotmatch(qreq_)
        >>> ut.show_if_requested()
    """
    # Unpack neighbor ids, indices, filter scores, and flags
    indexer = qreq_.indexer
    neighb_nnidx = neighb_idx.T[:-Knorm].T
    qfx_list = nns.qfx_list
    K = neighb_nnidx.T.shape[0]
    neighb_daid = indexer.get_nn_aids(neighb_nnidx)
    neighb_dfx = indexer.get_nn_featxs(neighb_nnidx)

    # Determine matches that are valid using all measurements
    neighb_valid_list_ = [neighb_valid0] + ut.filter_Nones(neighb_valid_list)
    neighb_valid_agg = np.logical_and.reduce(neighb_valid_list_)

    # We fill filter each relavant matrix by aggregate validity
    flat_validx = np.flatnonzero(neighb_valid_agg)
    # Infer the valid internal query feature indexes and ranks
    valid_x     = np.floor_divide(flat_validx, K, dtype=hstypes.INDEX_TYPE)
    valid_qfx   = qfx_list.take(valid_x)
    valid_rank  = np.mod(flat_validx, K, dtype=hstypes.FK_DTYPE)
    # Then take the valid indices from internal database
    # annot_rowids, feature indexes, and all scores
    valid_daid  = neighb_daid.take(flat_validx, axis=None)
    valid_dfx   = neighb_dfx.take(flat_validx, axis=None)
    valid_scorevec = np.concatenate(
        [neighb_score.take(flat_validx)[:, None]
         for neighb_score in neighb_score_list], axis=1)

    # Incorporate Normalizers
    # Normalizers for each weight filter that used a normalizer
    # Determine which feature per annot was used as the normalizer for each filter
    # Each non-None sub list is still in neighb_ format
    num_filts = len(neighb_normk_list)
    K = len(neighb_idx.T) - Knorm
    norm_filtxs = ut.where_not_None(neighb_normk_list)
    num_normed_filts = len(norm_filtxs)
    if num_normed_filts > 0:
        _normks = ut.take(neighb_normk_list, norm_filtxs)
        # Offset index to get flat normalizer positions
        _offset = np.arange(0, neighb_idx.size, neighb_idx.shape[1])
        flat_normxs = [_offset + neighb_normk for neighb_normk in _normks]
        flat_normidxs = [neighb_idx.take(ks) for ks in flat_normxs]
        flat_norm_aids = [indexer.get_nn_aids(idx)   for idx in flat_normidxs]
        flat_norm_fxs  = [indexer.get_nn_featxs(idx) for idx in flat_normidxs]
        # Take the valid indicies
        _valid_norm_aids = [aids.take(valid_x) for aids in flat_norm_aids]
        _valid_norm_fxs  = [fxs.take(valid_x)  for fxs in flat_norm_fxs]
    else:
        _valid_norm_aids = []
        _valid_norm_fxs = []
    valid_norm_aids = ut.ungroup([_valid_norm_aids], [norm_filtxs], num_filts - 1)
    valid_norm_fxs = ut.ungroup([_valid_norm_fxs], [norm_filtxs], num_filts - 1)

    # The q/d's are all internal here, thus in vsone they swap
    vmt = ValidMatchTup_(valid_daid, valid_qfx, valid_dfx, valid_scorevec,
                         valid_rank, valid_norm_aids, valid_norm_fxs)
    return vmt


#============================
# 5) Spatial Verification
#============================


def spatial_verification(qreq_, cm_list_FILT, verbose=VERB_PIPELINE):
    r"""
    pipeline step 5 - spatially verify feature matches

    Returns:
        list: cm_listSVER - new list of spatially verified chipmatches

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-spatial_verification --show
        python -m ibeis.algo.hots.pipeline --test-spatial_verification --show --qaid 1
        python -m ibeis.algo.hots.pipeline --test-spatial_verification:0

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST', qaid_list=[18])
        >>> scoring.score_chipmatch_list(qreq_, cm_list, qreq_.qparams.prescore_method)  # HACK
        >>> cm = cm_list[0]
        >>> top_nids = cm.get_top_nids(6)
        >>> verbose = True
        >>> cm_list_SVER = spatial_verification(qreq_, cm_list)
        >>> # Test Results
        >>> cmSV = cm_list_SVER[0]
        >>> scoring.score_chipmatch_list(qreq_, cm_list_SVER, qreq_.qparams.score_method)  # HACK
        >>> top_nids_SV = cmSV.get_top_nids(6)
        >>> cm.print_csv(sort=True)
        >>> cmSV.print_csv(sort=False)
        >>> gt_daids  = np.intersect1d(cm.get_groundtruth_daids(), cmSV.get_groundtruth_daids())
        >>> fm_list   = cm.get_annot_fm(gt_daids)
        >>> fmSV_list = cmSV.get_annot_fm(gt_daids)
        >>> maplen = lambda list_: np.array(list(map(len, list_)))
        >>> assert len(gt_daids) > 0, 'ground truth did not survive'
        >>> ut.assert_lessthan(maplen(fmSV_list), maplen(fm_list)), 'feature matches were not filtered'
        >>> ut.quit_if_noshow()
        >>> cmSV.show_daids_matches(qreq_, gt_daids)
        >>> import plottool as pt
        >>> #homog_tup = (refined_inliers, H)
        >>> #aff_tup = (aff_inliers, Aff)
        >>> #pt.draw_sv.show_sv(rchip1, rchip2, kpts1, kpts2, fm, aff_tup=aff_tup, homog_tup=homog_tup, refine_method=refine_method)
        >>> ut.show_if_requested()

    Ignore:
        idx = cm.daid2_idx[gt_daids[0]]
        idxSV = cmSV.daid2_idx[gt_daids[0]]
        cm.fm_list[idx]
        cmSV.fm_list[idxSV]
        cmSV.H_list[idxSV]

    Ignore:
        #print("NEIGHBOR HASH")
        #print(ut.hashstr(str(nns_list)))  # nondetermenism check
        # Find non-determenism
        python -m ibeis.dev -t custom:checks=100,sv_on=True   --db PZ_MTEST --rank-lt-list=1,5 --qaids=50,53 --nocache-hs --print-rowscore
        It is not here
        xn@c0v7bm7kr++jq - 9
        xn@c0v7bm7kr++jq - 2
        # somewhere in sver
        #ut.hashstr27(str([cm.fsv_list for cm in cm_list]))
        # cemglnqifyonhnnk
        #ut.hashstr27(str([cm.fsv_list for cm in cm_list_SVER]))
        # rcchbmgovmndlzuo
        #kpts1 = kpts1.astype(np.float64)
        #kpts2 = kpts2.astype(np.float64)
        #print(sv_tup[0])
        #print(sv_tup[3])
    """
    cm_list = cm_list_FILT
    if not qreq_.qparams.sv_on or qreq_.qparams.xy_thresh is None:
        if verbose:
            print('[hs] Step 5) Spatial verification: off')
        return cm_list
    else:
        cm_list_SVER = _spatial_verification(qreq_, cm_list, verbose=verbose)
        return cm_list_SVER


@profile
def _spatial_verification(qreq_, cm_list, verbose=VERB_PIPELINE):
    """
    make only spatially valid features survive
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
    """
    if verbose:
        print('[hs] Step 5) Spatial verification: ' + qreq_.qparams.sv_cfgstr)

    # TODO: move rerank out of theis pipeline node
    #with_metadata = qreq_.qparams.with_metadata
    # dbg info (can remove if there is a speed issue)
    score_method = qreq_.qparams.score_method
    prescore_method    = qreq_.qparams.prescore_method
    nNameShortList  = qreq_.qparams.nNameShortlistSVER
    nAnnotPerName   = qreq_.qparams.nAnnotPerNameSVER

    # Just in case we are csum scoring, this needs to be computed
    # FIXME: 'csum' is much faster than 'nsum'
    # and probably should be used pre-verification
    #for cm in cm_list:
    #    cm.evaluate_dnids(qreq_)
    #prescore_method = 'csum'
    scoring.score_chipmatch_list(qreq_, cm_list, prescore_method)
    cm_shortlist = scoring.make_chipmatch_shortlists(qreq_, cm_list,
                                                     nNameShortList,
                                                     nAnnotPerName,
                                                     score_method)
    prog_hook = None if qreq_.prog_hook is None else qreq_.prog_hook.next_subhook()
    cm_progiter = ut.ProgressIter(cm_shortlist, nTotal=len(cm_shortlist),
                                  prog_hook=prog_hook, lbl=SVER_LVL, **PROGKW)
    cm_list_SVER = [sver_single_chipmatch(qreq_, cm) for cm in cm_progiter]
    # rescore after verification?
    return cm_list_SVER


@profile
def sver_single_chipmatch(qreq_, cm):
    r"""
    Spatially verifies a shortlist of a single chipmatch

    TODO: move to chip match?

    loops over a shortlist of results for a specific query annotation

    Args:
        qreq_ (QueryRequest):  query request object with hyper-parameters
        cm (ChipMatch):

    Returns:
        ibeis.ChipMatch: cmSV

    CommandLine:
        python -m ibeis draw_rank_cdf --db PZ_Master1 --show \
            -t best:refine_method=[homog,affine,cv2-homog,cv2-ransac-homog,cv2-lmeds-homog] \
            -a timectrlhard ---acfginfo --veryverbtd

        python -m ibeis draw_rank_cdf --db PZ_Master1 --show \
            -t best:refine_method=[homog,cv2-lmeds-homog],full_homog_checks=[True,False] \
            -a timectrlhard ---acfginfo --veryverbtd

        python -m ibeis sver_single_chipmatch --show \
            -t default:full_homog_checks=True -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=affine -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=cv2-homog -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=cv2-homog,full_homog_checks=True -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=cv2-homog,full_homog_checks=False -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=cv2-lmeds-homog,full_homog_checks=False -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:refine_method=cv2-ransac-homog,full_homog_checks=False -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show \
            -t default:full_homog_checks=False -a default --qaid 18

        python -m ibeis sver_single_chipmatch --show --qaid=18 --y=0
        python -m ibeis sver_single_chipmatch --show --qaid=18 --y=1

    Example:
        >>> # DISABLE_DOCTEST
        >>> # Visualization
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> qreq_, args = plh.testdata_pre('spatial_verification', defaultdb='PZ_MTEST')  #, qaid_list=[18])
        >>> cm_list = args.cm_list_FILT
        >>> ibs = qreq_.ibs
        >>> cm = cm_list[0]
        >>> scoring.score_chipmatch_list(qreq_, cm_list, qreq_.qparams.prescore_method)  # HACK
        >>> #locals_ = ut.exec_func_src(sver_single_chipmatch, key_list=['svtup_list'], sentinal='# <SENTINAL>')
        >>> #svtup_list1, = locals_
        >>> source = ut.get_func_sourcecode(sver_single_chipmatch, stripdef=True, strip_docstr=True)
        >>> source = ut.replace_between_tags(source, '', '# <SENTINAL>', '# </SENTINAL>')
        >>> globals_ = globals().copy()
        >>> exec(source, globals_)
        >>> svtup_list = globals_['svtup_list']
        >>> gt_daids = cm.get_groundtruth_daids()
        >>> x = ut.get_argval('--y', type_=int, default=0)
        >>> #print('x = %r' % (x,))
        >>> #daid = daids[x % len(daids)]
        >>> notnone_list = ut.not_list(ut.flag_None_items(svtup_list))
        >>> valid_idxs = np.where(notnone_list)
        >>> valid_daids = cm.daid_list[valid_idxs]
        >>> assert len(valid_daids) > 0, 'cannot spatially verify'
        >>> valid_gt_daids = np.intersect1d(gt_daids, valid_daids)
        >>> #assert len(valid_gt_daids) == 0, 'no sver groundtruth'
        >>> daid = valid_gt_daids[x] if len(valid_gt_daids) > 0 else valid_daids[x]
        >>> idx = cm.daid2_idx[daid]
        >>> svtup = svtup_list[idx]
        >>> assert svtup is not None, 'SV TUP IS NONE'
        >>> refined_inliers, refined_errors, H = svtup[0:3]
        >>> aff_inliers, aff_errors, Aff = svtup[3:6]
        >>> homog_tup = (refined_inliers, H)
        >>> aff_tup = (aff_inliers, Aff)
        >>> fm = cm.fm_list[idx]
        >>> aid1 = cm.qaid
        >>> aid2 = daid
        >>> rchip1, = ibs.get_annot_chips([aid1], config2_=qreq_.extern_query_config2)
        >>> kpts1,  = ibs.get_annot_kpts([aid1], config2_=qreq_.extern_query_config2)
        >>> rchip2, = ibs.get_annot_chips([aid2], config2_=qreq_.extern_data_config2)
        >>> kpts2, = ibs.get_annot_kpts([aid2], config2_=qreq_.extern_data_config2)
        >>> import plottool as pt
        >>> show_aff = not ut.get_argflag('--noaff')
        >>> refine_method = qreq_.qparams.refine_method if not ut.get_argflag('--norefinelbl') else ''
        >>> pt.draw_sv.show_sv(rchip1, rchip2, kpts1, kpts2, fm, aff_tup=aff_tup,
        >>>                    homog_tup=homog_tup, show_aff=show_aff,
        >>>                    refine_method=refine_method)
        >>> ut.show_if_requested()
    """
    qaid = cm.qaid
    use_chip_extent       = qreq_.qparams.use_chip_extent
    xy_thresh             = qreq_.qparams.xy_thresh
    scale_thresh          = qreq_.qparams.scale_thresh
    ori_thresh            = qreq_.qparams.ori_thresh
    min_nInliers          = qreq_.qparams.min_nInliers
    full_homog_checks     = qreq_.qparams.full_homog_checks
    refine_method         = qreq_.qparams.refine_method
    sver_output_weighting = qreq_.qparams.sver_output_weighting
    # Precompute sver cmtup_old
    kpts1 = qreq_.ibs.get_annot_kpts(qaid, config2_=qreq_.extern_query_config2)
    kpts2_list = qreq_.ibs.get_annot_kpts(cm.daid_list,
                                          config2_=qreq_.extern_data_config2)
    if use_chip_extent:
        top_dlen_sqrd_list = qreq_.ibs.get_annot_chip_dlensqrd(
            cm.daid_list, config2_=qreq_.extern_data_config2)
    else:
        top_dlen_sqrd_list = compute_matching_dlen_extent(qreq_, cm.fm_list, kpts2_list)
    config2_ = qreq_.extern_query_config2
    if qreq_.qparams.weight_inliers:
        # Weights for inlier scoring
        qweights = scoring.get_annot_kpts_baseline_weights(
            qreq_.ibs, [qaid], config2_=config2_, config=config2_)[0].astype(np.float64)
        match_weight_list = [qweights.take(fm.T[0]) for fm in cm.fm_list]
    else:
        match_weight_list = [np.ones(len(fm), dtype=np.float64) for fm in cm.fm_list]

    # Make an svtup for every daid in the shortlist
    _iter1 = zip(cm.daid_list, cm.fm_list, cm.fsv_list, cm.fk_list, kpts2_list,
                 top_dlen_sqrd_list, match_weight_list)
    svtup_list = []
    for daid, fm, fsv, fk, kpts2, dlen_sqrd2, match_weights in _iter1:
        if len(fm) == 0:
            # skip results without any matches
            sv_tup = None
        else:
            try:
                # Compute homography from chip2 to chip1 returned homography
                # maps image1 space into image2 space image1 is a query chip
                # and image2 is a database chip
                sv_tup = vt.spatially_verify_kpts(
                    kpts1, kpts2, fm, xy_thresh, scale_thresh, ori_thresh,
                    dlen_sqrd2, min_nInliers, match_weights=match_weights,
                    full_homog_checks=full_homog_checks, refine_method=refine_method,
                    returnAff=True)
            except Exception as ex:
                ut.printex(ex, 'Unknown error in spatial verification.',
                           keys=['kpts1', 'kpts2',  'fm', 'xy_thresh',
                                 'scale_thresh', 'dlen_sqrd2', 'min_nInliers'])
                sv_tup = None
        svtup_list.append(sv_tup)

    # <SENTINAL>

    # New way
    if True:
        inliers_list = []
        for sv_tup in svtup_list:
            if sv_tup is None:
                inliers_list.append(None)
            else:
                (homog_inliers, homog_errors, H, aff_inliers, aff_errors, Aff) = sv_tup
                inliers_list.append(homog_inliers)

        indicies_list = inliers_list
        cmSV = cm.take_feature_matches(indicies_list, keepscores=False)

        # NOTE: It is not very clear explicitly, but the way H_list and
        # homog_err_weight_list are built will correspond with the daid_list in
        # cmSV returned by cm.take_feature_matches
        svtup_list_ = ut.filter_Nones(svtup_list)
        H_list_SV = ut.get_list_column(svtup_list_, 2)
        cmSV.H_list = H_list_SV

        if sver_output_weighting:
            homog_err_weight_list = []
            xy_thresh_sqrd = dlen_sqrd2 * xy_thresh
            for sv_tup in svtup_list_:
                (homog_inliers, homog_errors) = sv_tup[0:2]
                homog_xy_errors = homog_errors[0].take(homog_inliers, axis=0)
                homog_err_weight = (1.0 - np.sqrt(homog_xy_errors / xy_thresh_sqrd))
                homog_err_weight_list.append(homog_err_weight)
            # Rescore based on homography errors
            filtkey = hstypes.FiltKeys.HOMOGERR
            filtweight_list = homog_err_weight_list
            cmSV.append_featscore_column(filtkey, filtweight_list)
    else:
        # Remove all matches that failed spatial verification
        # TODO: change to list compress and numpy arrays
        flags = ut.flag_not_None_items(svtup_list)
        svtup_list_ = ut.compress(svtup_list, flags)
        daid_list   = ut.compress(cm.daid_list, flags)
        dnid_list   = ut.compress(cm.dnid_list, flags)
        fm_list     = ut.compress(cm.fm_list, flags)
        fsv_list    = ut.compress(cm.fsv_list, flags)
        fk_list     = ut.compress(cm.fk_list, flags)

        sver_matchtup_list = []
        fsv_col_lbls = cm.fsv_col_lbls[:]
        if sver_output_weighting:
            fsv_col_lbls += [hstypes.FiltKeys.HOMOGERR]

        for sv_tup, daid, fm, fsv, fk in zip(svtup_list_, daid_list, fm_list, fsv_list, fk_list):
            # Return the inliers to the homography from chip2 to chip1
            (homog_inliers, homog_errors, H, aff_inliers, aff_errors, Aff) = sv_tup
            fm_SV  = fm.take(homog_inliers, axis=0)
            fsv_SV = fsv.take(homog_inliers, axis=0)
            fk_SV  = fk.take(homog_inliers, axis=0)
            if sver_output_weighting:
                # Rescore based on homography errors
                xy_thresh_sqrd = dlen_sqrd2 * xy_thresh
                homog_xy_errors = homog_errors[0].take(homog_inliers, axis=0)
                homog_err_weight = (1.0 - np.sqrt(homog_xy_errors / xy_thresh_sqrd))
                homog_err_weight.shape = (homog_err_weight.size, 1)
                fsv_SV = np.concatenate((fsv_SV, homog_err_weight), axis=1)
            sver_matchtup_list.append((fm_SV, fsv_SV, fk_SV, H))

        fm_list_SV  = ut.get_list_column(sver_matchtup_list, 0)
        fsv_list_SV = ut.get_list_column(sver_matchtup_list, 1)
        fk_list_SV  = ut.get_list_column(sver_matchtup_list, 2)
        H_list_SV   = ut.get_list_column(sver_matchtup_list, 3)

        cmSV = chip_match.ChipMatch(
            qaid=cm.qaid, daid_list=daid_list,
            fm_list=fm_list_SV, fsv_list=fsv_list_SV, fk_list=fk_list_SV,
            H_list=H_list_SV, dnid_list=dnid_list, qnid=cm.qnid,
            fsv_col_lbls=fsv_col_lbls)
    return cmSV


def compute_matching_dlen_extent(qreq_, fm_list, kpts_list):
    r"""
    helper for spatial verification, computes the squared diagonal length of
    matching chips

    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-compute_matching_dlen_extent

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> ibs, qreq_, cm_list = plh.testdata_pre_sver('PZ_MTEST')
        >>> verbose = True
        >>> cm = cm_list[0]
        >>> cm.set_cannonical_annot_score(cm.get_num_matches_list())
        >>> cm.sortself()
        >>> fm_list = cm.fm_list
        >>> kpts_list = qreq_.ibs.get_annot_kpts(cm.daid_list.tolist(), config2_=qreq_.extern_data_config2)
        >>> topx2_dlen_sqrd = compute_matching_dlen_extent(qreq_, fm_list, kpts_list)
        >>> ut.assert_inbounds(np.sqrt(topx2_dlen_sqrd)[0:5], 600, 1500)

    """
    # Use extent of matching keypoints
    # first get matching keypoints
    fx2_list = [fm.T[1] for fm in fm_list]
    kpts2_m_list = vt.ziptake(kpts_list, fx2_list, axis=0)
    #[kpts.take(fx2, axis=0) for (kpts, fx2) in zip(kpts_list, fx2_list)]
    dlen_sqrd_list = [vt.get_kpts_dlen_sqrd(kpts2_m)
                      for kpts2_m in kpts2_m_list]
    return dlen_sqrd_list


#============================
# 5.5ish) Vsone Reranking
#============================


def vsone_reranking(qreq_, cm_list_SVER, verbose=VERB_PIPELINE):
    r"""
    CommandLine:
        python -m ibeis.algo.hots.pipeline --test-vsone_reranking
        python -m ibeis.algo.hots.pipeline --test-vsone_reranking --show

    Example2:
        >>> # SLOW_DOCTEST (IMPORTANT)
        >>> from ibeis.algo.hots.pipeline import *  # NOQA
        >>> import ibeis
        >>> cfgdict = dict(prescore_method='nsum', score_method='nsum', vsone_reranking=True)
        >>> p = 'default' + ut.get_cfg_lbl(cfgdict)
        >>> qreq_ = ibeis.testdata_qreq_(defaultdb='PZ_MTEST', p=[p], qaid_override=[2])
        >>> ibs = qreq_.ibs
        >>> locals_ = plh.testrun_pipeline_upto(qreq_, 'vsone_reranking')
        >>> cm_list = locals_['cm_list_SVER']
        >>> verbose = True
        >>> cm_list_VSONE = vsone_reranking(qreq_, cm_list, verbose=verbose)
        >>> ut.quit_if_noshow()
        >>> from ibeis.algo.hots import vsone_pipeline
        >>> import plottool as pt
        >>> # NOTE: the aid2_score field must have been hacked
        >>> vsone_pipeline.show_top_chipmatches(ibs, cm_list, 0,  'prescore')
        >>> vsone_pipeline.show_top_chipmatches(ibs, cm_list_VSONE,   1, 'vsone-reranked')
        >>> pt.show_if_requested()
    """
    from ibeis.algo.hots import vsone_pipeline
    if verbose:
        print('Step 5.5ish) vsone reranking')
    cm_list = cm_list_SVER
    cm_list_VSONE = vsone_pipeline.vsone_reranking(qreq_, cm_list, verbose)
    return cm_list_VSONE


if __name__ == '__main__':
    """
    python -m ibeis.algo.hots.pipeline --verb-test
    python -m ibeis.algo.hots.pipeline --test-build_chipmatches
    python -m ibeis.algo.hots.pipeline --test-spatial-verification
    python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0 --show
    python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:0 --show
    python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:1 --show --db NAUT_test
    python -m ibeis.algo.hots.pipeline --test-request_ibeis_query_L0:1 --db NAUT_test --noindent
    python -m ibeis.algo.hots.pipeline --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()
    ut.doctest_funcs()
    if ut.get_argflag('--show'):
        import plottool as pt
        exec(pt.present())
