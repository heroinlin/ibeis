# -*- coding: utf-8 -*-
"""
CommandLine:
    # Generate and start an IPython notebook
    python -m ibeis --tf autogen_ipynb --ipynb --db <dbname> [-a <acfg>] [-t <pcfg>]

    python -m ibeis --tf autogen_ipynb --ipynb --db seaturtles -a default2:qhas_any=\(left,right\),sample_occur=True,occur_offset=[0,1,2],num_names=1
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import utool as ut
from ibeis.templates import notebook_cells
from functools import partial


def autogen_ipynb(ibs, launch=None, run=None):
    r"""
    Autogenerates standard IBEIS Image Analysis IPython notebooks.

    CommandLine:
        python -m ibeis --tf autogen_ipynb --run --db lynx

        python -m ibeis --tf autogen_ipynb --ipynb --db PZ_MTEST --asreport
        python -m ibeis --tf autogen_ipynb --ipynb --db PZ_MTEST --noexample --withtags

        python -m ibeis --tf autogen_ipynb --db PZ_MTEST
        # TODO: Add support for dbdir to be specified
        python -m ibeis --tf autogen_ipynb --db ~/work/PZ_MTEST

        python -m ibeis --tf autogen_ipynb --ipynb --db Oxford -a default:qhas_any=\(query,\),dpername=1,exclude_reference=True,dminqual=good
        python -m ibeis --tf autogen_ipynb --ipynb --db PZ_MTEST -a default -t best:lnbnn_normalizer=[None,normlnbnn-test]

        python -m ibeis.templates.generate_notebook --exec-autogen_ipynb --db wd_peter_blinston --ipynb

        python -m ibeis --tf autogen_ipynb --db PZ_Master1 --ipynb
        python -m ibeis --tf autogen_ipynb --db PZ_Master1 -a timectrl:qindex=0:100 -t best best:normsum=True --ipynb --noexample
        python -m ibeis --tf autogen_ipynb --db PZ_Master1 -a timectrl --run
        jupyter-notebook Experiments-lynx.ipynb
        killall python

        python -m ibeis --tf autogen_ipynb --db humpbacks --ipynb -t default:proot=BC_DTW -a default:has_any=hasnotch
        python -m ibeis --tf autogen_ipynb --db humpbacks --ipynb -t default:proot=BC_DTW default:proot=vsmany -a default:has_any=hasnotch,mingt=2,qindex=0:50 --noexample

    Example:
        >>> # SCRIPT
        >>> from ibeis.templates.generate_notebook import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb(defaultdb='testdb1')
        >>> result = autogen_ipynb(ibs)
        >>> print(result)
    """
    dbname = ibs.get_dbname()
    fname = 'Experiments-' + dbname
    nb_fpath = fname + '.ipynb'
    if ut.get_argflag('--cells'):
        notebook_cells = make_ibeis_cell_list(ibs)
        print('\n# ---- \n'.join(notebook_cells))
        return
    # TODO: Add support for dbdir to be specified
    notebook_str = make_ibeis_notebook(ibs)
    ut.writeto(nb_fpath, notebook_str)
    run = ut.get_argflag('--run') if run is None else run
    launch = launch if launch is not None else ut.get_argflag('--ipynb')
    if run:
        run_nb = ut.run_ipython_notebook(notebook_str)
        output_fpath = ut.export_notebook(run_nb, fname)
        ut.startfile(output_fpath)
    elif launch:
        ut.cmd('jupyter-notebook', nb_fpath, detatch=True)
        #ut.cmd('ipython-notebook', nb_fpath)
        #ut.startfile(nb_fpath)
    else:
        print('notebook_str =\n%s' % (notebook_str,))


def get_default_cell_template_list(ibs):
    """
    Defines the order of ipython notebook cells
    """

    cells = notebook_cells

    noexample = ut.get_argflag('--noexample')
    asreport = ut.get_argflag('--asreport')
    withtags = ut.get_argflag('--withtags')

    cell_template_list = []

    info_cells = [
        cells.pipe_config_info,
        cells.annot_config_info,
        cells.timestamp_distribution,
    ]

    dev_analysis = [
        cells.config_overlap,
        #cells.dbsize_expt,
        None if ibs.get_dbname() == 'humpbacks' else cells.feat_score_sep,
        cells.all_annot_scoresep,
        cells.success_annot_scoresep,
    ]

    cell_template_list += [
        cells.introduction if asreport else None,
        cells.initialize,
        None if ibs.get_dbname() != 'humpbacks' else cells.fluke_select,
    ]

    if not asreport:
        cell_template_list += info_cells

    if not noexample:
        cell_template_list += [
            cells.example_annotations,
            cells.example_names,
        ]

    cell_template_list += [
        cells.per_annotation_accuracy,
        cells.per_name_accuracy,
        cells.easy_success_cases,
        cells.hard_success_cases,
        cells.failure_type1_cases,
        cells.failure_type2_cases,
        cells.timedelta_distribution,
    ]

    if withtags:
        cell_template_list += [
            cells.investigate_specific_case,
            cells.view_intereseting_tags,
        ]

    if asreport:
        # Append our debug stuff at the bottom
        cell_template_list += [cells.IGNOREAFTER]
        cell_template_list += info_cells

    cell_template_list += dev_analysis

    cell_template_list += [
        cells.config_disagree_cases,
    ]

    cell_template_list = ut.filter_Nones(cell_template_list)

    return cell_template_list


def make_ibeis_notebook(ibs):
    r"""
    Args:
        ibs (ibeis.IBEISController):  ibeis controller object

    CommandLine:
        python -m ibeis.templates.generate_notebook --exec-make_ibeis_notebook --db wd_peter_blinston --asreport
        python -m ibeis --tf --exec-make_ibeis_notebook
        python -m ibeis --tf make_ibeis_notebook --db lynx
        jupyter-notebook tmp.ipynb
        runipy tmp.ipynb --html report.html
        runipy --pylab tmp.ipynb tmp2.ipynb
        sudo pip install runipy
        python -c "import runipy; print(runipy.__version__)"

    Example:
        >>> # SCRIPT
        >>> from ibeis.templates.generate_notebook import *  # NOQA
        >>> import ibeis
        >>> ibs = ibeis.opendb(defaultdb='testdb1')
        >>> notebook_str = make_ibeis_notebook(ibs)
        >>> print(notebook_str)
    """
    cell_list = make_ibeis_cell_list(ibs)
    notebook_str = ut.make_notebook(cell_list)
    return notebook_str


def make_ibeis_cell_list(ibs):
    cell_template_list = get_default_cell_template_list(ibs)
    autogen_str = ut.make_autogen_str()
    dbname = ibs.get_dbname()
    default_acfgstr = ut.get_argval('-a', type_=str, default='default:is_known=True')

    asreport = ut.get_argflag('--asreport')

    default_pcfgstr_list = ut.get_argval(('-t', '-p'), type_=list, default='default')
    default_pcfgstr = ut.repr3(default_pcfgstr_list, nobr=True)

    if asreport:
        annotconfig_list_body = ut.codeblock(
            ut.repr2(default_acfgstr) )
        pipeline_list_body = ut.codeblock(
            default_pcfgstr
        )
    else:
        annotconfig_list_body = ut.codeblock(
            ut.repr2(default_acfgstr) + '\n' +
            ut.codeblock('''
            # See ibeis/expt/annotation_configs.py for names of annot configuration options
            #'default:has_any=(query,),dpername=1,exclude_reference=True',
            #'default:is_known=True',
            #'default:qsame_imageset=True,been_adjusted=True,excluderef=True,qsize=10,dsize=20',
            #'default:require_timestamp=True,min_timedelta=3600',
            #'default:species=primary',
            #'timectrl:',
            #'unctrl:been_adjusted=True',
            ''')
        )
        pipeline_list_body = ut.codeblock(
            default_pcfgstr + '\n' +
            ut.codeblock('''
            #'default',
            #'default:K=1,AI=False,QRH=True',
            #'default:K=1,RI=True,AI=False',
            #'default:K=1,adapteq=True',
            #'default:fg_on=[True,False]',
            ''')
        )

    locals_ = locals()
    _format = partial(ut.format_cells, locals_=locals_)
    cell_list = ut.flatten(map(_format, cell_template_list))
    return cell_list


if __name__ == '__main__':
    """
    CommandLine:
        python -m ibeis.templates.generate_notebook
        python -m ibeis.templates.generate_notebook --allexamples
        python -m ibeis.templates.generate_notebook --allexamples --noface --nosrc
    """
    import multiprocessing
    multiprocessing.freeze_support()  # for win32
    import utool as ut  # NOQA
    ut.doctest_funcs()
