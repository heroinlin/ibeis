# -*- coding: utf-8 -*-
"""
DEPRICATE FOR CORE ANNOT AND CORE IMAGE DEFS
"""
from __future__ import absolute_import, division, print_function
import utool as ut
import six
import copy
#import dtool
from os.path import join
from os.path import splitext
from six.moves import zip, map, range, filter  # NOQA
from ibeis import constants as const
from utool._internal.meta_util_six import get_funcname
(print, rrr, profile) = ut.inject2(__name__, '[cfg]')

#ConfigBase = ut.DynStruct
#ConfigBase = object
ConfigBase = ut.Pref


def parse_config_items(cfg):
    """
    Recursively extracts key, val pairs from Config objects
    into a flat list. (there must not be name conflicts)

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> cfg = ibs.cfg.query_cfg
        >>> param_list = parse_config_items(cfg)
    """
    import ibeis
    param_list = []
    seen = set([])
    for item in cfg.items():
        key, val = item
        if isinstance(val, ibeis.algo.Config.ConfigBase):
            child_cfg = val
            param_list.extend(parse_config_items(child_cfg))
            #print(key)
            pass
        elif key.startswith('_'):
            #print(key)
            pass
        else:
            if key in seen:
                print('[Config] WARNING: key=%r appears more than once' %
                      (key,))
            seen.add(key)
            param_list.append(item)
            #print(key)
    return param_list


def make_config_metaclass():
    """
    Creates a metaclass for Config objects that automates some of the more
    tedious functions to write

    Like:
        get_cfgstr
        and the comparison methods


    Example:
        from ibeis.algo.Config import *  # NOQA
        @six.add_metaclass(ConfigMetaclass)
        class FooConfig(ConfigBase):
            def __init__(cfg):
                super(FooConfig, cfg).__init__(name='FooConfig')
                cfg.initialize_params()

            def get_param_info_list(cfg):
                return [
                    ut.ParamInfo('x', 'y'),
                    ut.ParamInfo('z', 3),
                ]
        cfg = FooConfig()
        print(cfg.get_cfgstr(ignore_keys=['x']))
        print(cfg.get_cfgstr(ignore_keys=[]))

        cfg = GenericConfig()
        cfg.x = 'y'

    """
    methods_list = ut.get_comparison_methods()

    # Decorator for functions that we will inject into our metaclass
    def _register(func):
        methods_list.append(func)
        return func

    @_register
    def get_cfgstr_list(cfg, ignore_keys=None, **kwargs):
        """ default get_cfgstr_list, can be overrided by a config object """
        if hasattr(cfg, 'get_param_info_list'):
            if ignore_keys is not None:
                itemstr_list = [pi.get_itemstr(cfg)
                                for pi in cfg.get_param_info_list()
                                if pi.varname not in ignore_keys]
            else:
                itemstr_list = [pi.get_itemstr(cfg)
                                for pi in cfg.get_param_info_list()]
        else:
            try:
                item_list = parse_config_items(cfg)
                assert item_list is not None
                if ignore_keys is None:
                    itemstr_list = [key + '=' + str(val) for key, val in item_list]
                else:
                    itemstr_list = [key + '=' + str(val) for key, val in item_list if key not in ignore_keys]
            except Exception as ex:
                print(ignore_keys is None)
                print(ignore_keys)
                ut.printex(ex, keys=['item_list', 'ignore_keys'])
                raise
        filtered_itemstr_list = list(filter(len, itemstr_list))
        config_name = cfg.get_config_name()
        body = ','.join(filtered_itemstr_list)
        cfgstr = ''.join(['_', config_name, '(', body, ')'])
        return cfgstr

    @_register
    def initialize_params(cfg):
        """ Initializes config class attributes based on params info list """
        for pi in cfg.get_param_info_list():
            setattr(cfg, pi.varname, pi.default)

    @_register
    def parse_items(cfg, **kwargs):
        return parse_config_items(cfg)

    @_register
    def keys(cfg, **kwargs):
        return ut.take_column(cfg.parse_items(), 0)

    @_register
    def get_config_name(cfg, **kwargs):
        """ the user might want to overwrite this function """
        class_str = str(cfg.__class__)
        full_class_str = class_str.replace('<class \'', '').replace('\'>', '')
        config_name = splitext(full_class_str)[1][1:].replace('Config', '')
        return config_name

    @_register
    def __hash__(cfg):
        """ Needed for comparison operators """
        return hash(cfg.get_cfgstr())

    @_register
    def get_cfgstr(cfg, **kwargs):
        return ''.join(cfg.get_cfgstr_list(**kwargs))

    @_register
    def lookup_paraminfo(cfg, key):
        for pi in cfg.get_param_info_list():
            if pi.varname == key:
                return pi
        raise KeyError('no such param info (in the old config)')

    class ConfigMetaclass(type):
        """
        Defines extra methods for Configs
        """

        def __new__(cls, name, bases, dct):
            """
            cls - meta
            name - classname
            supers - bases
            dct - class dictionary
            """
            #assert 'get_cfgstr_list' in dct, (
            #  'must have defined get_cfgstr_list.  name=%r' % (name,))
            # Inject registered function
            for func in methods_list:
                if get_funcname(func) not in dct:
                    funcname = get_funcname(func)
                    dct[funcname] = func
                else:
                    funcname = get_funcname(func)
                    dct['meta_' + funcname] = func
                #ut.inject_func_as_method(metaself, func)
            return type.__new__(cls, name, bases, dct)

    return ConfigMetaclass

ConfigMetaclass = make_config_metaclass()


@six.add_metaclass(ConfigMetaclass)
class GenericConfig(ConfigBase):
    def __init__(cfg, *args, **kwargs):
        super(GenericConfig, cfg).__init__(*args, **kwargs)


@six.add_metaclass(ConfigMetaclass)
class NNConfig(ConfigBase):
    r"""
    CommandLine:
        python -m ibeis.algo.Config --exec-NNConfig

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> nn_cfg = NNConfig()
        >>> nn_cfg = NNConfig(single_name_condition=True)
        >>> result = nn_cfg.get_cfgstr()
        >>> print(result)
        _NN(single,K=4,Kn=1,padk=False,cks800)
    """
    def __init__(nn_cfg, **kwargs):
        super(NNConfig, nn_cfg).__init__()
        #if True:
        nn_cfg.initialize_params()
        #else:
        #    nn_cfg.K = 4
        #    # TODO: force to false when in vsone
        #    nn_cfg.use_k_padding = False
        #    # number of annots before a new multi-indexer is built
        #    #nn_cfg.min_reindex_thresh = 3
        #    #nn_cfg.index_method = 'multi'
        #    nn_cfg.index_method = 'single'
        #    nn_cfg.Knorm = 1
        #    nn_cfg.checks = 800
        # number of annots before a new multi-indexer is built
        nn_cfg.min_reindex_thresh = 200
        # number of annots before a new multi-indexer is built
        nn_cfg.max_subindexers = 2
        nn_cfg.valid_index_methods = ['single', 'multi', 'name']
        nn_cfg.update(**kwargs)

    def make_feasible(nn_cfg):
        # normalizer rule depends on Knorm
        assert nn_cfg.index_method in nn_cfg.valid_index_methods

    def get_param_info_list(rrvsone_cfg):
        # new way to try and specify config options.
        # not sure if i like it yet
        param_info_list = ut.flatten([
            [
                ut.ParamInfo('index_method', 'single', ''),
                ut.ParamInfo('K', 4, type_=int),
                ut.ParamInfo('Knorm', 1, 'Kn='),
                ut.ParamInfo('use_k_padding', False, 'padk='),
                ut.ParamInfo('single_name_condition', False, 'nameknn', type_=bool, hideif=False),
                ut.ParamInfo('checks', 800, 'cks', type_=int),
                #ut.ParamInfo('ratio_thresh', None, type_=float, hideif=None),
            ],
        ])
        return param_info_list


@six.add_metaclass(ConfigMetaclass)
class SpatialVerifyConfig(ConfigBase):
    """
    Spatial verification
    """
    def __init__(sv_cfg, **kwargs):
        super(SpatialVerifyConfig, sv_cfg).__init__(name='sv_cfg')
        tau = 6.28  # 318530
        sv_cfg.sv_on = True
        sv_cfg.xy_thresh = .01
        sv_cfg.scale_thresh = 2.0
        sv_cfg.ori_thresh   = tau / 4.0
        sv_cfg.min_nInliers = 4
        sv_cfg.full_homog_checks = True
        sv_cfg.nNameShortlistSVER = 50
        sv_cfg.nAnnotPerNameSVER = 6
        #sv_cfg.prescore_method = 'csum'
        sv_cfg.prescore_method = 'nsum'
        sv_cfg.use_chip_extent = True  # BAD CONFIG?
        # weight feature scores with sver errors
        sv_cfg.sver_output_weighting = False
        sv_cfg.refine_method = 'homog'
        # weight feature scores with sver errors
        sv_cfg.weight_inliers = True
        sv_cfg.update(**kwargs)

    def get_cfgstr_list(sv_cfg, **kwargs):
        if not sv_cfg.sv_on or sv_cfg.xy_thresh is None:
            return ['_SV(OFF)']
        thresh_tup = (sv_cfg.xy_thresh, sv_cfg.scale_thresh, sv_cfg.ori_thresh)
        thresh_str = ut.remove_chars(str(thresh_tup), ' ()').replace(',', ';')
        sv_cfgstr = [
            '_SV(',
            thresh_str,
            'minIn=%d,' % (sv_cfg.min_nInliers,),
            'nNRR=%d,' % (sv_cfg.nNameShortlistSVER,),
            'nARR=%d,' % (sv_cfg.nAnnotPerNameSVER,),
            sv_cfg.prescore_method, ',',
            'cdl,' * sv_cfg.use_chip_extent,  # chip diag len
            '+ow,' * sv_cfg.sver_output_weighting,  # chip diag len
            '+wi,' * sv_cfg.weight_inliers,  # chip diag len
            '+fc,' * sv_cfg.full_homog_checks,
        ]

        if sv_cfg.refine_method != 'homog':
            sv_cfgstr += [sv_cfg.refine_method]

        sv_cfgstr += [
            ')',
        ]
        return sv_cfgstr


@six.add_metaclass(ConfigMetaclass)
class AggregateConfig(ConfigBase):
    """
    Old Agg Cfg
    """
    def __init__(agg_cfg, **kwargs):
        super(AggregateConfig, agg_cfg).__init__(name='agg_cfg')
        # chipsum, namesum, placketluce
        #agg_cfg.score_method = 'csum'
        agg_cfg.score_method = 'nsum'
        agg_cfg.score_normalization = None
        agg_cfg.normsum = False
        #agg_cfg.score_normalization = True
        alt_methods = {
            'topk': 'topk',
            'borda': 'borda',
            'placketluce': 'pl',
            'chipsum': 'csum',
            'namesum': 'nsum',
            'coverage': 'coverage',
        }
        # For Placket-Luce
        agg_cfg.max_alts = 50
        #-----
        # User update
        agg_cfg.update(**kwargs)
        # ---
        key = agg_cfg.score_method.lower()
        # Use w as a toggle for weighted mode
        # Sanatize the scoring method
        if key in alt_methods:
            agg_cfg.score_method = alt_methods[key]

    def get_cfgstr_list(agg_cfg, **kwargs):
        agg_cfgstr = []
        agg_cfgstr.append('_AGG(')
        agg_cfgstr.append(agg_cfg.score_method)
        if agg_cfg.score_method  == 'pl':
            agg_cfgstr.append(',%d' % (agg_cfg.max_alts,))
        if agg_cfg.score_normalization:
            agg_cfgstr.append(',norm')
        if agg_cfg.normsum:
            agg_cfgstr.append(',normsum')
        agg_cfgstr.append(')')
        return agg_cfgstr


@six.add_metaclass(ConfigMetaclass)
class FlannConfig(ConfigBase):
    r"""
    this flann is only for neareset neighbors in vsone/many
    TODO: this might not need to be here, should be part of neighbor config

    References:
        http://www.cs.ubc.ca/research/flann/uploads/FLANN/flann_pami2014.pdf
        http://www.cs.ubc.ca/research/flann/uploads/FLANN/flann_manual-1.8.4.pdf
        http://docs.opencv.org/trunk/modules/flann/doc/flann_fast_approximate_nearest_neighbor_search.html
    """
    def __init__(flann_cfg, **kwargs):
        super(FlannConfig, flann_cfg).__init__(name='flann_cfg')
        #General Params
        flann_cfg.algorithm = 'kdtree'  # linear
        flann_cfg.flann_cores = 0  # doesnt change config, just speed
        # KDTree params
        flann_cfg.trees = 8
        # KMeansTree params
        flann_cfg.iterations = 11
        flann_cfg.centers_init = 'random'
        flann_cfg.cb_index = .4
        flann_cfg.branching = 64
        # THESE CONFIGS DONT BELONG TO FLANN. THEY ARE INDEXER CONFIGS
        flann_cfg.fgw_thresh = None
        flann_cfg.minscale_thresh = None
        flann_cfg.maxscale_thresh = None
        flann_cfg.update(**kwargs)

    def get_flann_params(flann_cfg):
        flann_params = dict(
            algorithm=flann_cfg.algorithm,
            trees=flann_cfg.trees,
            cores=flann_cfg.flann_cores,
        )
        return flann_params

    def get_cfgstr_list(flann_cfg, **kwargs):
        flann_cfgstrs = ['_FLANN(']
        if flann_cfg.algorithm == 'kdtree':
            flann_cfgstrs += ['%d_kdtrees' % flann_cfg.trees]
        elif flann_cfg.algorithm == 'kdtree':
            flann_cfgstrs += [
                '%s_' % flann_cfg.algorithm,
                'iter=%s_' % flann_cfg.iterations,
                'cb=%s_' % flann_cfg.cb_index,
                'branch=%s' % flann_cfg.branching,
            ]
        elif flann_cfg.algorithm == 'linear':
            flann_cfgstrs += ['%s' % flann_cfg.algorithm]
        else:
            flann_cfgstrs += ['%s' % flann_cfg.algorithm]
        if flann_cfg.fgw_thresh is not None and flann_cfg.fgw_thresh > 0:
            # HACK FOR GGR
            flann_cfgstrs += ['_fgwthrsh=%s' % flann_cfg.fgw_thresh]
        if (flann_cfg.minscale_thresh is not None) or (flann_cfg.maxscale_thresh is not None):
            # HACK FOR GGR
            flann_cfgstrs += ['scalethrsh=%s,%s' % (flann_cfg.minscale_thresh, flann_cfg.maxscale_thresh)]
        #flann_cfgstrs += ['checks=%r' % flann_cfg.checks]
        flann_cfgstrs += [')']
        return flann_cfgstrs


@six.add_metaclass(ConfigMetaclass)
class SMKConfig(ConfigBase):
    """

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> smk_cfg = SMKConfig()
        >>> result1 = smk_cfg.get_cfgstr()
        >>> print(result1)

    Example2:
        >>> # ENABLE_DOCTEST
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> smk_cfg = ibs.cfg.query_cfg.smk_cfg
        >>> smk_cfg.printme3()
    """
    def __init__(smk_cfg, **kwargs):
        super(SMKConfig, smk_cfg).__init__(name='smk_cfg')
        smk_cfg.smk_thresh = 0.0  # tau in the paper
        smk_cfg.smk_alpha  = 3.0
        smk_cfg.smk_aggregate  = False
        # TODO Separate into vocab config
        smk_cfg._valid_vocab_weighting = ['idf', 'negentropy']
        smk_cfg.vocab_weighting = 'idf'
        smk_cfg.allow_self_match = False
        smk_cfg.vocabtrain_cfg = VocabTrainConfig(**kwargs)
        smk_cfg.vocabassign_cfg = VocabAssignConfig(**kwargs)
        smk_cfg.update(**kwargs)

    def make_feasible(smk_cfg):

        hasvalid_weighting = any([
            smk_cfg.vocab_weighting == x
            for x in smk_cfg._valid_vocab_weighting])
        assert hasvalid_weighting, (
            'invalid vocab weighting %r' % smk_cfg.vocab_weighting)

    def get_cfgstr_list(smk_cfg, **kwargs):
        smk_cfgstr_list = [
            '_SMK(',
            'agg=', str(smk_cfg.smk_aggregate),
            ',t=', str(smk_cfg.smk_thresh),
            ',a=', str(smk_cfg.smk_alpha),
            ',SelfOk' if smk_cfg.allow_self_match else '',
            ',%s' % smk_cfg.vocab_weighting,
            ')',
        ]
        smk_cfgstr_list.extend(smk_cfg.vocabassign_cfg.get_cfgstr_list())
        smk_cfgstr_list.extend(smk_cfg.vocabtrain_cfg.get_cfgstr_list())
        return smk_cfgstr_list


@six.add_metaclass(ConfigMetaclass)
class VocabTrainConfig(ConfigBase):
    """

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> vocabtrain_cfg = VocabTrainConfig()
        >>> result = vocabtrain_cfg.get_cfgstr()
        >>> print(result)

    """
    def __init__(vocabtrain_cfg, **kwargs):
        super(VocabTrainConfig, vocabtrain_cfg).__init__(
            name='vocabtrain_cfg')
        vocabtrain_cfg.override_vocab = 'default'  # Vocab
        vocabtrain_cfg.vocab_taids = 'all'  # Vocab
        vocabtrain_cfg.nWords = int(8E3)  #
        vocabtrain_cfg.vocab_init_method = 'akmeans++'
        vocabtrain_cfg.vocab_nIters = 128
        # TODO: easy flann params cfgstr
        vocabtrain_cfg.vocab_flann_params = dict(cores=0)
        vocabtrain_cfg.update(**kwargs)

    def get_cfgstr_list(vocabtrain_cfg, **kwargs):
        if vocabtrain_cfg.override_vocab == 'default':
            if isinstance(vocabtrain_cfg.vocab_taids, six.string_types):
                taids_cfgstr = 'taids=%s' % vocabtrain_cfg.vocab_taids
            else:
                taids_cfgstr = ut.hashstr_arr(vocabtrain_cfg.vocab_taids,
                                              'taids', hashlen=8)
            vocabtrain_cfg_list = [
                '_VocabTrain(',
                'nWords=%d' % (vocabtrain_cfg.nWords,),
                ',init=', str(vocabtrain_cfg.vocab_init_method),
                ',nIters=%d,' % int(vocabtrain_cfg.vocab_nIters),
                taids_cfgstr,
                ')',
            ]
        else:
            vocabtrain_cfg_list = ['_VocabTrain(override=%s)' %
                                   (vocabtrain_cfg.override_vocab,)]
        return vocabtrain_cfg_list


@six.add_metaclass(ConfigMetaclass)
class VocabAssignConfig(ConfigBase):
    """

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> vocabassign_cfg = VocabAssignConfig()
        >>> result = vocabassign_cfg.get_cfgstr()
        >>> print(result)
    """
    def __init__(vocabassign_cfg, **kwargs):
        super(VocabAssignConfig, vocabassign_cfg).__init__(
            name='vocabassign_cfg')
        vocabassign_cfg.nAssign = 10  # MultiAssignment
        vocabassign_cfg.massign_equal_weights = True
        vocabassign_cfg.massign_alpha = 1.2
        vocabassign_cfg.massign_sigma = 80.0
        vocabassign_cfg.update(**kwargs)

    def make_feasible(vocabassign_cfg):
        assert vocabassign_cfg.nAssign > 0, 'cannot assign to nothing'
        if vocabassign_cfg.nAssign == 1:
            # No point to multiassign weights if nAssign is 1
            vocabassign_cfg.massign_equal_weights = True

        if vocabassign_cfg.massign_equal_weights:
            # massign sigma makes no difference if there are equal weights
            vocabassign_cfg.massign_sigma = None

    def get_cfgstr_list(vocabassign_cfg, **kwargs):
        vocabassign_cfg_list = [
            '_VocabAssign(',
            'nAssign=', str(vocabassign_cfg.nAssign),
            ',a=', str(vocabassign_cfg.massign_alpha),
            ',s=', (str(vocabassign_cfg.massign_sigma)
                    if vocabassign_cfg.massign_equal_weights else ''),
            ',eqw=T' if vocabassign_cfg.massign_equal_weights else ',eqw=F',
            ')',
        ]
        return vocabassign_cfg_list


@six.add_metaclass(ConfigMetaclass)
class NNWeightConfig(ConfigBase):
    r"""
    CommandLine:
        python -m ibeis.algo.Config --test-NNWeightConfig

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> cfg_list = [
        ...     NNWeightConfig(),
        ...     NNWeightConfig(can_match_sameimg=True, can_match_samename=False),
        ...     NNWeightConfig(ratio_thresh=.625, lnbnn_on=False),
        ...     NNWeightConfig(ratio_thresh=.625, lnbnn_normer='foobarstr'),
        ... ]
        >>> result = '\n'.join([cfg.get_cfgstr() for cfg in cfg_list])
        >>> print(result)
        _NNWeight(lnbnn,fg,last,nosqrd_dist)
        _NNWeight(lnbnn,fg,last,sameimg,nosamename,nosqrd_dist)
        _NNWeight(ratio_thresh=0.625,fg,last,nosqrd_dist)
        _NNWeight(ratio_thresh=0.625,lnbnn,fg,last,lnbnn_normer=foobarstr,lnbnn_norm_thresh=0.5,nosqrd_dist)
    """
    def __init__(nnweight_cfg, **kwargs):
        super(NNWeightConfig, nnweight_cfg).__init__(name='nnweight_cfg')
        nnweight_cfg.initialize_params()
        nnweight_cfg.update(**kwargs)

    def get_param_info_list(nnweight_cfg):
        # new way to try and specify config options.
        # not sure if i like it yet
        param_info_list = ut.flatten([
            [
                ut.ParamInfo('ratio_thresh', None, type_=float, hideif=None),
                ut.ParamInfoBool('lnbnn_on', True,  hideif=False),
                ut.ParamInfoBool('const_on', False,  hideif=False),
                ut.ParamInfoBool('borda_on', False,  hideif=False),
                ut.ParamInfoBool('lograt_on', False, hideif=False),
                #ut.ParamInfoBool('loglnbnn_on', False,  hideif=False),
                #ut.ParamInfoBool('logdist_on', False,  hideif=False),
                #ut.ParamInfoBool('dist_on', False,  hideif=False),
                ut.ParamInfoBool('normonly_on', False,  hideif=False),
                ut.ParamInfoBool('bar_l2_on', False,  hideif=False),
                ut.ParamInfoBool('cos_on', False,  hideif=False),
                ut.ParamInfoBool('fg_on', True, hideif=False),
                ut.ParamInfo('normalizer_rule', 'last', '', valid_values=['last', 'name']),
                ut.ParamInfo('lnbnn_normer', None,  hideif=None,
                             help_='config string for lnbnn score normalizer'),
                ut.ParamInfo('lnbnn_norm_thresh', .5, type_=float,
                             hideif=lambda cfg: not cfg['lnbnn_normer'] ,
                             help_='config string for lnbnn score normalizer'),
                #
                ut.ParamInfoBool('can_match_sameimg', False,  'sameimg',
                                 hideif=False),
                ut.ParamInfoBool('can_match_samename', True, 'samename',
                                 hideif=True),
                # Hacked in
                #ut.ParamInfoBool('root_sift_on', False,  hideif=False),
                ut.ParamInfoBool('sqrd_dist_on', False,  hideif=True),
                #ut.ParamInfoBool('sqrd_dist_on', True,  hideif=True),
            ],
        ])
        return param_info_list


@six.add_metaclass(ConfigMetaclass)
class RerankVsOneConfig(ConfigBase):
    """
    CommandLine:
        python -m ibeis.algo.Config --test-RerankVsOneConfig

    Example0:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> rrvsone_cfg = RerankVsOneConfig(rrvsone_on=True)
        >>> result = rrvsone_cfg.get_cfgstr()
        >>> assert result.startswith('_RRVsOne(True,')

    Example1:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> rrvsone_cfg = RerankVsOneConfig(rrvsone_on=True)
        >>> result = rrvsone_cfg.get_cfgstr()
        >>> print(result)
        _RRVsOne(True,nNm=20,nApN=3,prior_coeff=0.6,unc_coeff=0.4,sver_unc=True,uncRat=0.8)

    """
    def __init__(rrvsone_cfg, **kwargs):
        super(RerankVsOneConfig, rrvsone_cfg).__init__(name='rrvsone_cfg')
        rrvsone_cfg.initialize_params()
        rrvsone_cfg.update(**kwargs)

    def get_config_name(rrvsone_cfg):
        return 'RRVsOne'

    def get_param_info_list(rrvsone_cfg):
        from ibeis.algo.hots import distinctiveness_normalizer
        from ibeis.algo.hots import vsone_pipeline
        # new way to try and specify config options.
        # not sure if i like it yet
        param_info_list = ut.flatten([
            [
                ut.ParamInfo('rrvsone_on', False, ''),
            ],
            vsone_pipeline.OTHER_RRVSONE_PARAMS.aslist(),
            vsone_pipeline.SHORTLIST_DEFAULTS.aslist(),
            vsone_pipeline.COEFF_DEFAULTS.aslist(),
            vsone_pipeline.UNC_DEFAULTS.aslist(),
            vsone_pipeline.SCR_DEFAULTS.aslist(),
            vsone_pipeline.COVKPTS_DEFAULT.aslist(
                hideif=lambda cfg: not cfg['covscore_on'] or cfg['maskscore_mode'] != 'kpts'),
            vsone_pipeline.COVGRID_DEFAULT.aslist(
                hideif=lambda cfg: not cfg['covscore_on'] or cfg['maskscore_mode'] != 'grid'),
            distinctiveness_normalizer.DCVS_DEFAULT.aslist(
                hideif=lambda cfg: not cfg['dcvs_on']),
        ])
        return param_info_list

    def get_constraint_func():
        # TODO:
        def constraint_func(cfg):
            if cfg['rrvsone_on']:
                return False
            if cfg['use_gridcov_scoring'] and cfg['use_kptscov_scoring']:
                return False

    def get_cfgstr_list(rrvsone_cfg, **kwargs):
        if rrvsone_cfg.rrvsone_on:
            rrvsone_cfg_list = rrvsone_cfg.meta_get_cfgstr_list(**kwargs)
        else:
            rrvsone_cfg_list = [
                '_RRVsOne(',
                str(rrvsone_cfg.rrvsone_on),
                ')'
            ]
        return rrvsone_cfg_list


@six.add_metaclass(ConfigMetaclass)
class QueryConfig(ConfigBase):
    """
    query configuration parameters

    Example:
        >>> # ENABLE_DOCTEST
        >>> import ibeis
        >>> ibs = ibeis.opendb('testdb1')
        >>> cfg = ibs.cfg.query_cfg
        >>> cfgstr = ibs.cfg.query_cfg.get_cfgstr()
        >>> print(cfgstr)

    """
    def __init__(query_cfg, **kwargs):
        super(QueryConfig, query_cfg).__init__(name='query_cfg')
        query_cfg.nn_cfg         = NNConfig(**kwargs)
        query_cfg.nnweight_cfg   = NNWeightConfig(**kwargs)
        query_cfg.sv_cfg         = SpatialVerifyConfig(**kwargs)
        query_cfg.agg_cfg        = AggregateConfig(**kwargs)
        query_cfg.flann_cfg      = FlannConfig(**kwargs)
        query_cfg.smk_cfg        = SMKConfig(**kwargs)
        query_cfg.rrvsone_cfg    = RerankVsOneConfig(**kwargs)
        # causes some bug in Preference widget if these don't have underscore
        query_cfg._featweight_cfg = FeatureWeightConfig(**kwargs)
        query_cfg.use_cache = False
        # Start of pipeline
        query_cfg._valid_pipeline_roots = ['vsmany', 'vsone', 'smk', 'BC_DTW']
        query_cfg.pipeline_root = 'vsmany'
        # <Hack Paramaters>
        query_cfg.with_metadata = False
        query_cfg.augment_queryside_hack = False
        # for hacky distinctivness
        query_cfg.return_expanded_nns = False
        # for distinctivness model
        query_cfg.use_external_distinctiveness = False
        query_cfg.codename = 'None'
        query_cfg.species_code = '____'  # TODO: make use of this
        # </Hack Paramaters>
        #if ut.is_developer():
        #    query_cfg.pipeline_root = 'smk'
        # Depends on feature config
        query_cfg.update_query_cfg(**kwargs)
        if ut.VERYVERBOSE:
            print('[config] NEW QueryConfig')

    def get_cfgstr_list(query_cfg, **kwargs):
        # Ensure feasibility of the configuration
        query_cfg.make_feasible()

        # Build cfgstr
        cfgstr_list = ['_' + query_cfg.pipeline_root ]
        if str(query_cfg.pipeline_root) == 'smk':
            # SMK Parameters
            if kwargs.get('use_smk', True):
                cfgstr_list += query_cfg.smk_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_sv', True):
                cfgstr_list += query_cfg.sv_cfg.get_cfgstr_list(**kwargs)
        elif str(query_cfg.pipeline_root) == 'vsmany' or str(query_cfg.pipeline_root) == 'vsone':
            # Naive Bayes Parameters
            if kwargs.get('use_nn', True):
                cfgstr_list += query_cfg.nn_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_nnweight', True):
                cfgstr_list += query_cfg.nnweight_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_sv', True):
                cfgstr_list += query_cfg.sv_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_agg', True):
                cfgstr_list += query_cfg.agg_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_flann', True):
                cfgstr_list += query_cfg.flann_cfg.get_cfgstr_list(**kwargs)
            if kwargs.get('use_rrvsone', True):
                cfgstr_list += query_cfg.rrvsone_cfg.get_cfgstr_list(**kwargs)
        else:
            raise AssertionError('bad pipeline root: ' + str(query_cfg.pipeline_root))
        if kwargs.get('use_featweight', True):
            cfgstr_list += query_cfg._featweight_cfg.get_cfgstr_list(**kwargs)
            # HACK: featweight_cfg used to include chip and feat
            # but they arent working now due to new structures, so they are hacked in here
            # This whole file will eventually be depricated
            cfgstr_list += query_cfg._featweight_cfg._feat_cfg.get_cfgstr_list(**kwargs)
            cfgstr_list += query_cfg._featweight_cfg._feat_cfg._chip_cfg.get_cfgstr_list(**kwargs)

        if query_cfg.augment_queryside_hack:
            # HACK
            cfgstr_list += ['_HACK(augment_queryside)']
        return cfgstr_list

    def update_query_cfg(query_cfg, **cfgdict):
        # Each config paramater should be unique
        # So updating them all should not cause conflicts
        # FIXME: Should be able to infer all the children that need updates
        #
        # apply codename before updating subconfigs
        query_cfg.apply_codename(cfgdict.get('codename', None))
        # update subconfigs
        query_cfg.nn_cfg.update(**cfgdict)
        query_cfg.nnweight_cfg.update(**cfgdict)
        query_cfg.sv_cfg.update(**cfgdict)
        query_cfg.agg_cfg.update(**cfgdict)
        query_cfg.flann_cfg.update(**cfgdict)
        query_cfg.smk_cfg.update(**cfgdict)
        query_cfg.smk_cfg.vocabassign_cfg.update(**cfgdict)
        query_cfg.smk_cfg.vocabtrain_cfg.update(**cfgdict)
        query_cfg.rrvsone_cfg.update(**cfgdict)
        query_cfg._featweight_cfg.update(**cfgdict)
        query_cfg._featweight_cfg._feat_cfg.update(**cfgdict)
        query_cfg._featweight_cfg._feat_cfg._chip_cfg.update(**cfgdict)
        query_cfg.update(**cfgdict)
        # Ensure feasibility of the configuration
        try:
            query_cfg.make_feasible()
        except AssertionError as ex:
            print(ut.dict_str(cfgdict, sorted_=True))
            ut.printex(ex)
            raise

    def apply_codename(query_cfg, codename=None):
        """
        codenames denote mass changes to configurations
        it is a hacky solution to setting different parameter
        values all at once.
        """
        if codename is None:
            codename = query_cfg.codename

        nnweight_cfg = query_cfg.nnweight_cfg
        nn_cfg   = query_cfg.nn_cfg
        agg_cfg = query_cfg.agg_cfg

        if codename.startswith('csum') or codename.endswith('_csum'):
            raise NotImplementedError('codename nsum')
        if codename.startswith('nsum'):
            raise NotImplementedError('codename nsum')
        if codename.startswith('vsmany'):
            query_cfg.pipeline_root = 'vsmany'
        elif codename.startswith('vsone'):
            query_cfg.pipeline_root = 'vsone'
            nn_cfg.K = 1
            nn_cfg.Knorm = 1
            nnweight_cfg.lnbnn_on = False
            #nnweight_cfg.ratio_thresh = 1.6
            if codename.endswith('_dist') or '_dist_' in codename:
                # no ratio use distance
                nnweight_cfg.ratio_thresh = None
                nnweight_cfg.dist_on = True
            else:
                nnweight_cfg.ratio_thresh = .625
            if '_ratio' in codename:
                nnweight_cfg.ratio_thresh = .625
            if '_extern_distinctiveness' in codename:
                query_cfg.use_external_distinctiveness = True
            if codename.startswith('vsone_unnorm'):
                agg_cfg.score_normalization = None
            elif codename.startswith('vsone_norm'):
                agg_cfg.score_normalization = 'vsone_default'
        elif codename.startswith('asmk'):
            query_cfg.pipeline_root = 'asmk'
        elif codename.startswith('smk'):
            query_cfg.pipeline_root = 'smk'
        elif codename == 'None':
            pass

    def make_feasible(query_cfg):
        try:
            query_cfg.make_feasible_()
        except AssertionError as ex:
            if ut.NOT_QUIET:
                query_cfg.printme3()
            ut.printex(ex, 'failed ot make feasible')
            raise

    def make_feasible_(query_cfg):
        """
        removes invalid parameter settings over all cfgs (move to QueryConfig)
        """
        nnweight_cfg = query_cfg.nnweight_cfg
        nn_cfg   = query_cfg.nn_cfg
        featweight_cfg = query_cfg._featweight_cfg
        #feat_cfg = query_cfg._featweight_cfg._feat_cfg
        smk_cfg = query_cfg.smk_cfg
        vocabassign_cfg = query_cfg.smk_cfg.vocabassign_cfg
        agg_cfg = query_cfg.agg_cfg
        #sv_cfg = query_cfg.sv_cfg

        #assert sv_cfg.prescore_method == agg_cfg.score_method, 'cannot be
        # different yet.'

        if agg_cfg.score_normalization and query_cfg.pipeline_root == 'vsmany':
            assert agg_cfg.score_method == 'nsum'

        if query_cfg.pipeline_root == 'asmk':
            query_cfg.pipeline_root = 'smk'
            smk_cfg.smk_aggregate = True

        hasvalid_root = any([
            query_cfg.pipeline_root.lower() == root.lower()
            for root in query_cfg._valid_pipeline_roots])
        try:
            assert hasvalid_root, (
                'invalid pipeline root %r valid roots are %r' % query_cfg.pipeline_root, query_cfg._valid_pipeline_roots)
        except AssertionError as ex:
            ut.printex(ex)
            raise
            #if ut.SUPER_STRICT:
            #    raise
            #else:
            #    query_cfg.pipeline_root = query_cfg._valid_pipeline_roots[0]
            #    pass

        # HACK
        if nnweight_cfg.fg_on is not True:
            featweight_cfg.featweight_enabled = False
        if featweight_cfg.featweight_enabled is not True:
            nnweight_cfg.fg_on = False

        vocabassign_cfg.make_feasible()
        smk_cfg.make_feasible()
        #nnweight_cfg.make_feasible()
        nn_cfg.make_feasible()

    def deepcopy(query_cfg, **kwargs):
        copy_ = copy.deepcopy(query_cfg)
        copy_.update_query_cfg(**kwargs)
        return copy_


@six.add_metaclass(ConfigMetaclass)
class FeatureWeightConfig(ConfigBase):
    """

    CommandLine:
        python -m ibeis.algo.Config --exec-FeatureWeightConfig

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> featweight_cfg = FeatureWeightConfig(fw_detector='rf',
        >>>                                      featweight_enabled=True)
        >>> result = featweight_cfg.get_cfgstr()
        >>> print(result)

        _FEATWEIGHT(ON,uselabel,rf)_FEAT(hesaff+sift_)_CHIP(sz450)

        _FEATWEIGHT(OFF)_FEAT(hesaff+sift_)_CHIP(sz450)

    """

    def __init__(featweight_cfg, **kwargs):
        super(FeatureWeightConfig, featweight_cfg).__init__(
            name='featweight_cfg')
        # Featweights depend on features
        featweight_cfg._feat_cfg = FeatureConfig(**kwargs)
        featweight_cfg.initialize_params()
        # Feature weights depend on the detector, but we only need to mirror
        # some parameters because featweight_cfg should not use the detect_cfg
        # object
        #featweight_cfg.featweight_enabled = False
        #featweight_cfg.featweight_enabled = True
        #featweight_cfg.featweight_species  = 'uselabel'
        #featweight_cfg.fw_detector = 'rf'
        #featweight_cfg.fw_detector = 'cnn'
        featweight_cfg.update(**kwargs)

    def make_feasible(featweight_cfg):
        #featweight_cfg.featweight_enabled = False
        pass

    def get_param_info_list(self):
        from ibeis import core_annots
        return core_annots.ProbchipConfig._param_info_list + core_annots.FeatWeightConfig._param_info_list

    #def get_cfgstr_list(featweight_cfg, **kwargs):
    #    featweight_cfg.make_feasible()
    #    featweight_cfgstrs = []
    #    if kwargs.get('use_featweight', True):
    #        if featweight_cfg.featweight_enabled is not True:
    #            if featweight_cfg.featweight_enabled == 'ERR':
    #                featweight_cfgstrs.extend(['_FEATWEIGHT(ERR)'])
    #            else:
    #                featweight_cfgstrs.extend(['_FEATWEIGHT(OFF)'])
    #        else:
    #            featweight_cfgstrs.extend([
    #                '_FEATWEIGHT(ON',
    #                ',' + featweight_cfg.featweight_species,
    #                ',' + featweight_cfg.fw_detector,
    #                ')'])
    #    _cfgstrlist = featweight_cfg._feat_cfg.get_cfgstr_list(**kwargs)
    #    featweight_cfgstrs.extend(_cfgstrlist)
    #    return featweight_cfgstrs


@six.add_metaclass(ConfigMetaclass)
class FeatureConfig(ConfigBase):
    """
    Feature configuration object.

    TODO depcirate for core_annots.FeatConfig

    CommandLine:
        python -m ibeis.algo.Config --test-FeatureConfig

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo import Config  # NOQA
        >>> from ibeis.algo.Config import *  # NOQA
        >>> feat_cfg = Config.FeatureConfig()
        >>> result = (feat_cfg.get_cfgstr())
        >>> print(result)
        >>> #assert result.startswith('_FEAT(hesaff+sift_)_CHIP')
        _Feat(hesaff+sift)
    """
    def __init__(feat_cfg, **kwargs):
        # Features depend on chips
        #import pyhesaff
        super(FeatureConfig, feat_cfg).__init__(name='feat_cfg')
        feat_cfg._chip_cfg = ChipConfig(**kwargs)
        feat_cfg.initialize_params()
        #feat_cfg.feat_type = 'hesaff+sift'
        #feat_cfg.bgmethod = None
        #feat_cfg._param_list = list(six.iteritems(
        #    pyhesaff.get_hesaff_default_params()))
        #for type_, name, default, doc in feat_cfg._iterparams():
        #    setattr(feat_cfg, name, default)
        #feat_cfg.use_adaptive_scale = False  # 9001 # 80
        #feat_cfg.nogravity_hack = False  # 9001 # 80
        feat_cfg.update(**kwargs)

    def get_param_info_list(self):
        from ibeis import core_annots
        return core_annots.FeatConfig().get_param_info_list()

    def get_config_name(self):
        return 'Feat'

    def get_hesaff_params(feat_cfg):
        import pyhesaff
        default_keys = list(pyhesaff.get_hesaff_default_params().keys())
        hesaff_param_dict = ut.dict_subset(feat_cfg, default_keys)
        return hesaff_param_dict


@six.add_metaclass(ConfigMetaclass)
class ChipConfig(ConfigBase):
    """ ChipConfig """
    def __init__(cc_cfg, **kwargs):
        super(ChipConfig, cc_cfg).__init__(name='chip_cfg')
        cc_cfg.initialize_params()
        #cc_cfg.dim_size    = 450
        ##cc_cfg.resize_dim  = 'area'
        #cc_cfg.resize_dim  = 'width'
        #cc_cfg.grabcut     = False
        #cc_cfg.histeq      = False
        #cc_cfg.adapteq     = False
        #cc_cfg.region_norm = False
        #cc_cfg.rank_eq     = False
        #cc_cfg.local_eq    = False
        #cc_cfg.maxcontrast = False
        #cc_cfg.chipfmt     = '.png'
        cc_cfg.update(**kwargs)

    def get_param_info_list(self):
        from ibeis import core_annots
        return core_annots.ChipConfig._param_info_list


@six.add_metaclass(ConfigMetaclass)
class DetectionConfig(ConfigBase):
    """
    CommandLine:
        python -m ibeis.algo.Config --test-DetectionConfig

    Example:
        >>> # ENABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> detect_cfg = DetectionConfig()
        >>> result = (detect_cfg.get_cfgstr())
        >>> print(result)
        _DETECT(cnn,____,sz=800)
    """
    def __init__(detect_cfg, **kwargs):
        super(DetectionConfig, detect_cfg).__init__(name='detect_cfg')
        #detect_cfg.species_text = 'zebra_grevys'
        detect_cfg.species_text = const.UNKNOWN
        # detect_cfg.detector = 'rf'
        detect_cfg.detector = 'cnn'
        detect_cfg.scale_list  = '1.25, 1.0, 0.80, 0.65, 0.50, 0.40, 0.30, 0.20, 0.10'
        detect_cfg.trees_path  = ''
        detect_cfg.detectimg_sqrt_area = 800
        detect_cfg.update(**kwargs)

    def get_cfgstr_list(detect_cfg):
        cfgstrs = ['_DETECT(',
                   detect_cfg.detector,
                   ',', detect_cfg.species_text,
                   ',sz=%d' % (detect_cfg.detectimg_sqrt_area,),
                   ')']
        return cfgstrs


@six.add_metaclass(ConfigMetaclass)
class OccurrenceConfig(ConfigBase):
    """ OccurrenceConfig

    CommandLine:
        python -m ibeis.algo.Config --exec-OccurrenceConfig --show

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> occur_cfg = OccurrenceConfig()
        >>> print(occur_cfg.get_cfgstr())
    """
    def __init__(occur_cfg, **kwargs):
        super(OccurrenceConfig, occur_cfg).__init__(name='occur_cfg')
        occur_cfg.initialize_params()
        occur_cfg.update(**kwargs)

    def get_param_info_list(occur_cfg):
        param_info_list = [
            ut.ParamInfo('min_imgs_per_occurrence', 1, 'minper='),
            #ut.ParamInfo('cluster_algo', 'agglomerative', '', valid_values=['agglomerative', 'meanshift']),
            ut.ParamInfo('cluster_algo', 'agglomerative', '', valid_values=['agglomerative']),
            #ut.ParamInfo('quantile', .01, 'quant', hideif=lambda cfg: cfg['cluster_algo'] != 'meanshift'),
            ut.ParamInfo('seconds_thresh', 600, 'sec', hideif=lambda cfg: cfg['cluster_algo'] != 'agglomerative'),
            ut.ParamInfo('use_gps', True, hideif=False),
            ut.ParamInfo('km_per_sec', .002)
        ]
        return param_info_list


@six.add_metaclass(ConfigMetaclass)
class DisplayConfig(ConfigBase):
    """ DisplayConfig """
    def __init__(display_cfg, **kwargs):
        super(DisplayConfig, display_cfg).__init__(name='display_cfg')
        display_cfg.N = 6
        display_cfg.name_scoring = False
        display_cfg.showanalysis = False
        display_cfg.annotations  = True
        display_cfg.vert = True  # None
        display_cfg.show_results_in_image = False  # None

    def get_cfgstr_list(nn_cfg):
        raise NotImplementedError('abstract')
        return ['unimplemented']


@six.add_metaclass(ConfigMetaclass)
class OtherConfig(ConfigBase):
    def __init__(other_cfg, **kwargs):
        super(OtherConfig, other_cfg).__init__(name='other_cfg')
        #other_cfg.thumb_size      = 128
        other_cfg.thumb_size      = 221
        other_cfg.thumb_bare_size = 700
        other_cfg.ranks_top        = 2
        other_cfg.filter_reviewed = True
        other_cfg.auto_localize   = True
        # maximum number of exemplars per name
        other_cfg.max_exemplars   = 6
        other_cfg.exemplars_per_view  = 2
        other_cfg.prioritized_subset_annots_per_name  = 2
        other_cfg.exemplar_distinctiveness_thresh  = .95
        other_cfg.detect_add_after = 1
        # other_cfg.detect_use_chunks = True
        other_cfg.use_more_special_imagesets = True
        other_cfg.location_for_names = 'IBEIS'
        #other_cfg.location_for_names = 'MUGU'
        other_cfg.smart_enabled = True
        other_cfg.enable_custom_filter = False
        other_cfg.hots_batch_size = 256
        other_cfg.use_augmented_indexer = True
        other_cfg.show_shipped_imagesets = ut.is_developer()
        other_cfg.update(**kwargs)


# Convinience
def __dict_default_func(dict_):
    # Sets keys only if they dont exist
    def set_key(key, val):
        if key not in dict_:
            dict_[key] = val
    return set_key


def default_vsone_cfg(ibs, **kwargs):
    # DEPRICATE
    kwargs['pipeline_root'] = 'vsone'
    ut.dict_update_newkeys(kwargs, {
        'lnbnn_on': False,
        'checks': 256, 'K': 1,
        'Knorm': 1,
        'ratio_thresh': .6666  # 1.5,
    })
    query_cfg = QueryConfig(**kwargs)
    return query_cfg


def set_query_cfg(cfg, query_cfg):
    """ hack 12-30-2014 """
    cfg.query_cfg = query_cfg
    cfg.featweight_cfg = cfg.query_cfg._featweight_cfg
    cfg.feat_cfg       = cfg.query_cfg._featweight_cfg._feat_cfg
    cfg.chip_cfg       = cfg.query_cfg._featweight_cfg._feat_cfg._chip_cfg


def update_query_config(cfg, **kwargs):
    """ hack 12-30-2014 """
    cfg.query_cfg.update_query_cfg(**kwargs)
    cfg.featweight_cfg = cfg.query_cfg._featweight_cfg
    cfg.feat_cfg       = cfg.query_cfg._featweight_cfg._feat_cfg
    cfg.chip_cfg       = cfg.query_cfg._featweight_cfg._feat_cfg._chip_cfg


def load_named_config(cfgname, dpath, use_config_cache=False,
                      verbose=ut.VERBOSE and ut.NOT_QUIET):
    """ hack 12-30-2014

    Args:
        cfgname (str):
        dpath (str):
        use_config_cache (bool):

    Returns:
        Config: cfg

    CommandLine:
        python -m ibeis.algo.Config --test-load_named_config

    Example:
        >>> # DISABLE_DOCTEST
        >>> from ibeis.algo.Config import *  # NOQA
        >>> from ibeis.algo.Config import _default_config  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb('PZ_Master0')
        >>> #ibs.cfg.save()
        >>> # build test data
        >>> cfgname = 'zebra_plains'
        >>> dpath = ibs.get_dbdir()
        >>> use_config_cache = True
        >>> # execute function
        >>> cfg = load_named_config(cfgname, dpath, use_config_cache)
        >>> #
        >>> keys1 = ut.get_list_column(cfg.parse_items(), 0)
        >>> keys2 = ut.get_list_column(ibs.cfg.parse_items(), 0)
        >>> symdiff = set(keys1) ^ set(keys2)
        >>> # verify results
        >>> result = str(cfg)
        >>> print(result)
    """
    if cfgname is None:
        # TODO: find last cfgname
        cfgname = 'cfg'
    fpath = join(dpath, cfgname) + '.cPkl'
    if verbose:
        print('[Config] loading named config fpath=%r' % (fpath,))
    # Always a fresh object
    cfg = GenericConfig(cfgname, fpath=fpath)
    try:
        # Use pref cache
        if not use_config_cache:
            raise Exception('force config cache miss')
        # Get current "schema"
        tmp = _default_config(cfg, cfgname, new=True)
        current_itemset = tmp.parse_items()
        current_keyset = list(ut.get_list_column(current_itemset, 0))
        # load saved preferences
        cfg.load()
        # Check if loaded schema has changed
        loaded_keyset = list(ut.get_list_column(cfg.parse_items(), 0))
        missing_keys = set(current_keyset) - set(loaded_keyset)
        if len(missing_keys) != 0:
            # Bring over new values into old structure
            tmp.update(**dict(cfg.parse_items()))
            cfg = tmp
            #missing_vals = ut.dict_take(dict(current_itemset), missing_keys)
            #def find_cfgkey_parent(tmp, key):
            #    subconfig_list = []
            #    for attr in dir(tmp):
            #        if attr == key:
            #            return tmp
            #        child = getattr(tmp, attr)
            #        if isinstance(child, ConfigBase):
            #            subconfig_list.append(child)
            #    for subconfig in subconfig_list:
            #        found = find_cfgkey_parent(subconfig, key)
            #        if found is not None:
            #            return found
            #missing_parents = [find_cfgkey_parent(tmp, key) for key in missing_keys]
            #for parent, key, val in zip(missing_parents, missing_keys, missing_vals):
            #    setattr(parent, key, val)
        #    # TODO: Finishme update the out of data preferences
        #    pass
        if verbose:
            print('[Config] successfully loaded config cfgname=%r' % (cfgname,))
    except Exception as ex:
        if ut.VERBOSE:
            ut.printex(ex, iswarning=True)
        # Totally new completely default preferences
        cfg = _default_config(cfg, cfgname)
    # Hack in cfgname
    if verbose:
        print('[Config] hack in z_cfgname=%r' % (cfgname,))
    cfg.z_cfgname = cfgname
    return cfg


def _default_config(cfg, cfgname=None, new=True):
    """ hack 12-30-2014 """
    if ut.VERBOSE:
        print('[Config] building default config')
    if cfgname is None:
        cfgname = cfg.z_cfgname
    if new:
        fpath = cfg.get_fpath()
        cfg = GenericConfig(cfgname, fpath=fpath)
        cfg.z_cfgname = cfgname
    query_cfg = QueryConfig(pipeline_root='vsmany')
    set_query_cfg(cfg, query_cfg)
    cfg.occur_cfg   = OccurrenceConfig()
    cfg.detect_cfg  = DetectionConfig()
    cfg.other_cfg   = OtherConfig()
    _default_named_config(cfg, cfgname)
    #if len(species_list) == 1:
    #    # try to be intelligent about the default speceis
    #    cfg.detect_cfg.species_text = species_list[0]
    return cfg


def _default_named_config(cfg, cfgname):
    """ hack 12-30-2014

    list default parameters per species

    """
    if cfgname == 'cfg':
        cfg.detect_cfg.species_text = 'none'
    elif cfgname == 'zebra_plains':
        cfg.detect_cfg.species_text = cfgname
        #speedup': 46.90769958496094,
        cfg.query_cfg.flann_cfg.algorithm = 'kdtree'
        cfg.query_cfg.flann_cfg.trees = 8
        cfg.query_cfg.nn_cfg.checks = 704
        #'algorithm': 'kdtree',
        #[dev.tune_flann]    'checks': 6656,
        #[dev.tune_flann]    'trees': 4,

        # Kmeans seems a bit more accurate
        #'algorithm': 'kmeans',
        #'branching': 16,
        #'cb_index': 0.6000000238418579,
        #'centers_init': 'random',
        #'checks': 18432,
        #'iterations': 1,
        #'leaf_max_size': 4,
        #'speedup': 65.54280090332031,
        #'target_precision': 0.9800000190734863,

    elif cfgname == 'zebra_grevys':
        cfg.detect_cfg.species_text = cfgname
        #speedup': 224.7425994873047,
        cfg.query_cfg.flann_cfg.algorithm = 'kdtree'
        cfg.query_cfg.flann_cfg.trees = 4
        cfg.query_cfg.nn_cfg.checks = 896
    elif cfgname == 'giraffe_reticulated':
        cfg.detect_cfg.species_text = cfgname
        cfg.query_cfg.flann_cfg.algorithm = 'kdtree'
        cfg.query_cfg.flann_cfg.trees = 8
        cfg.query_cfg.nn_cfg.checks = 316
    else:
        if ut.VERBOSE:
            print('WARNING: UNKNOWN CFGNAME=%r' % (cfgname,))


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.algo.Config
        python -m ibeis.algo.Config --allexamples
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
