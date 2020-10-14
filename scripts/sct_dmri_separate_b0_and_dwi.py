#!/usr/bin/env python
#########################################################################################
#
# Separate b=0 and DW images from diffusion dataset.
#
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2013 Polytechnique Montreal <www.neuro.polymtl.ca>
# Author: Julien Cohen-Adad
# Modified: 2014-08-14
#
# About the license: see the file LICENSE.TXT
#########################################################################################

from __future__ import division, absolute_import

import sys
import math
import time
import os

import numpy as np

import sct_utils as sct
from spinalcordtoolbox.image import Image
from sct_image import split_data
from sct_convert import convert

from spinalcordtoolbox.utils import Metavar, SmartFormatter, ActionCreateFolder, init_sct, run_proc, tmp_create
import argparse


class Param:
    def __init__(self):
        self.debug = 0
        self.average = 1
        self.remove_temp_files = 1
        self.verbose = 1
        self.bval_min = 100  # in case user does not have min bvalues at 0, set threshold.


def get_parser():
    # Initialize parser
    param_default = Param()
    parser = argparse.ArgumentParser(
        description="Separate b=0 and DW images from diffusion dataset. The output files will have a suffix "
                    "(_b0 and _dwi) appended to the input file name.",
        formatter_class=SmartFormatter,
        add_help=None,
        prog=os.path.basename(__file__).strip(".py")
    )

    mandatory = parser.add_argument_group("\nMANDATORY ARGUMENTS")
    mandatory.add_argument(
        '-i',
        metavar=Metavar.file,
        required=True,
        help="Diffusion data. Example: dmri.nii.gz"
    )
    mandatory.add_argument(
        '-bvec',
        metavar=Metavar.file,
        required=True,
        help="Bvecs file. Example: bvecs.txt"
    )

    optional = parser.add_argument_group("\nOPTIONAL ARGUMENTS")
    optional.add_argument(
        "-h",
        "--help",
        action="help",
        help="Show this help message and exit."
    )
    optional.add_argument(
        '-a',
        type=int,
        choices=(0, 1),
        default=param_default.average,
        help="Average b=0 and DWI data. 0 = no, 1 = yes"
    )
    optional.add_argument(
        '-bval',
        metavar=Metavar.file,
        default="",
        help='bvals file. Used to identify low b-values (in case different from 0). Example: bvals.nii.gz',
    )
    optional.add_argument(
        '-bvalmin',
        type=float,
        metavar=Metavar.float,
        help='B-value threshold (in s/mm2) below which data is considered as b=0. Example: 50.0',
    )
    optional.add_argument(
        '-ofolder',
        metavar=Metavar.folder,
        action=ActionCreateFolder,
        default='./',
        help='Output folder. Example: dmri_separate_results/',
    )
    optional.add_argument(
        "-r",
        choices=('0', '1'),
        default=param_default.remove_temp_files,
        help="Remove temporary files. 0 = no, 1 = yes"
    )
    optional.add_argument(
        '-v',
        choices=('0', '1'),
        default=param_default.verbose,
        help='Verbose. 0 = nothing, 1 = expanded',
    )
    return parser


# MAIN
# ==========================================================================================
def main(args=None):
    # initialize parameters
    param = Param()
    # call main function
    parser = get_parser()
    if args:
        arguments = parser.parse_args(args)
    else:
        arguments = parser.parse_args(args=None if sys.argv[1:] else ['--help'])

    fname_data = arguments.i
    fname_bvecs = arguments.bvec
    average = arguments.a
    verbose = int(arguments.v)
    init_sct(log_level=verbose, update=True)  # Update log level
    remove_temp_files = arguments.r
    path_out = arguments.ofolder

    fname_bvals = arguments.bval
    if arguments.bvalmin:
        param.bval_min = arguments.bvalmin

    # Initialization
    start_time = time.time()

    # sct.printv(arguments)
    sct.printv('\nInput parameters:', verbose)
    sct.printv('  input file ............' + fname_data, verbose)
    sct.printv('  bvecs file ............' + fname_bvecs, verbose)
    sct.printv('  bvals file ............' + fname_bvals, verbose)
    sct.printv('  average ...............' + str(average), verbose)

    # Get full path
    fname_data = os.path.abspath(fname_data)
    fname_bvecs = os.path.abspath(fname_bvecs)
    if fname_bvals:
        fname_bvals = os.path.abspath(fname_bvals)

    # Extract path, file and extension
    path_data, file_data, ext_data = sct.extract_fname(fname_data)

    # create temporary folder
    path_tmp = tmp_create(basename="dmri_separate")

    # copy files into tmp folder and convert to nifti
    sct.printv('\nCopy files into temporary folder...', verbose)
    ext = '.nii'
    dmri_name = 'dmri'
    b0_name = file_data + '_b0'
    b0_mean_name = b0_name + '_mean'
    dwi_name = file_data + '_dwi'
    dwi_mean_name = dwi_name + '_mean'

    if not convert(fname_data, os.path.join(path_tmp, dmri_name + ext)):
        sct.printv('ERROR in convert.', 1, 'error')
    sct.copy(fname_bvecs, os.path.join(path_tmp, "bvecs"), verbose=verbose)

    # go to tmp folder
    curdir = os.getcwd()
    os.chdir(path_tmp)

    # Get size of data
    im_dmri = Image(dmri_name + ext)
    sct.printv('\nGet dimensions data...', verbose)
    nx, ny, nz, nt, px, py, pz, pt = im_dmri.dim
    sct.printv('.. ' + str(nx) + ' x ' + str(ny) + ' x ' + str(nz) + ' x ' + str(nt), verbose)

    # Identify b=0 and DWI images
    sct.printv(fname_bvals)
    index_b0, index_dwi, nb_b0, nb_dwi = identify_b0(fname_bvecs, fname_bvals, param.bval_min, verbose)

    # Split into T dimension
    sct.printv('\nSplit along T dimension...', verbose)
    im_dmri_split_list = split_data(im_dmri, 3)
    for im_d in im_dmri_split_list:
        im_d.save()

    # Merge b=0 images
    sct.printv('\nMerge b=0...', verbose)
    from sct_image import concat_data
    l = []
    for it in range(nb_b0):
        l.append(dmri_name + '_T' + str(index_b0[it]).zfill(4) + ext)
    im_out = concat_data(l, 3).save(b0_name + ext)

    # Average b=0 images
    if average:
        sct.printv('\nAverage b=0...', verbose)
        run_proc(['sct_maths', '-i', b0_name + ext, '-o', b0_mean_name + ext, '-mean', 't'], verbose)

    # Merge DWI
    l = []
    for it in range(nb_dwi):
        l.append(dmri_name + '_T' + str(index_dwi[it]).zfill(4) + ext)
    im_out = concat_data(l, 3).save(dwi_name + ext)

    # Average DWI images
    if average:
        sct.printv('\nAverage DWI...', verbose)
        run_proc(['sct_maths', '-i', dwi_name + ext, '-o', dwi_mean_name + ext, '-mean', 't'], verbose)

    # come back
    os.chdir(curdir)

    # Generate output files
    fname_b0 = os.path.abspath(os.path.join(path_out, b0_name + ext_data))
    fname_dwi = os.path.abspath(os.path.join(path_out, dwi_name + ext_data))
    fname_b0_mean = os.path.abspath(os.path.join(path_out, b0_mean_name + ext_data))
    fname_dwi_mean = os.path.abspath(os.path.join(path_out, dwi_mean_name + ext_data))
    sct.printv('\nGenerate output files...', verbose)
    sct.generate_output_file(os.path.join(path_tmp, b0_name + ext), fname_b0, verbose=verbose)
    sct.generate_output_file(os.path.join(path_tmp, dwi_name + ext), fname_dwi, verbose=verbose)
    if average:
        sct.generate_output_file(os.path.join(path_tmp, b0_mean_name + ext), fname_b0_mean, verbose=verbose)
        sct.generate_output_file(os.path.join(path_tmp, dwi_mean_name + ext), fname_dwi_mean, verbose=verbose)

    # Remove temporary files
    if remove_temp_files == 1:
        sct.printv('\nRemove temporary files...', verbose)
        sct.rmtree(path_tmp, verbose=verbose)

    # display elapsed time
    elapsed_time = time.time() - start_time
    sct.printv('\nFinished! Elapsed time: ' + str(int(np.round(elapsed_time))) + 's', verbose)

    return fname_b0, fname_b0_mean, fname_dwi, fname_dwi_mean


# ==========================================================================================
# identify b=0 and DW images
# ==========================================================================================
def identify_b0(fname_bvecs, fname_bvals, bval_min, verbose):

    # Identify b=0 and DWI images
    sct.printv('\nIdentify b=0 and DWI images...', verbose)
    index_b0 = []
    index_dwi = []

    # if bval is not provided
    if not fname_bvals:
        # Open bvecs file
        bvecs = []
        with open(fname_bvecs) as f:
            for line in f:
                bvecs_new = [x for x in map(float, line.split())]
                bvecs.append(bvecs_new)

        # Check if bvecs file is nx3
        if not len(bvecs[0][:]) == 3:
            sct.printv('  WARNING: bvecs file is 3xn instead of nx3. Consider using sct_dmri_transpose_bvecs.', verbose, 'warning')
            sct.printv('  Transpose bvecs...', verbose)
            # transpose bvecs
            bvecs = list(zip(*bvecs))

        # get number of lines
        nt = len(bvecs)

        # identify b=0 and dwi
        for it in range(0, nt):
            if math.sqrt(math.fsum([i**2 for i in bvecs[it]])) < 0.01:
                index_b0.append(it)
            else:
                index_dwi.append(it)

    # if bval is provided
    else:

        # Open bvals file
        from dipy.io import read_bvals_bvecs
        bvals, bvecs = read_bvals_bvecs(fname_bvals, fname_bvecs)

        # get number of lines
        nt = len(bvals)

        # Identify b=0 and DWI images
        sct.printv('\nIdentify b=0 and DWI images...', verbose)
        for it in range(0, nt):
            if bvals[it] < bval_min:
                index_b0.append(it)
            else:
                index_dwi.append(it)

    # check if no b=0 images were detected
    if index_b0 == []:
        sct.printv('ERROR: no b=0 images detected. Maybe you are using non-null low bvals? in that case use flag -bvalmin. Exit program.', 1, 'error')
        sys.exit(2)

    # display stuff
    nb_b0 = len(index_b0)
    nb_dwi = len(index_dwi)
    sct.printv('  Number of b=0: ' + str(nb_b0) + ' ' + str(index_b0), verbose)
    sct.printv('  Number of DWI: ' + str(nb_dwi) + ' ' + str(index_dwi), verbose)

    # return
    return index_b0, index_dwi, nb_b0, nb_dwi


# START PROGRAM
# ==========================================================================================
if __name__ == "__main__":
    init_sct()
    main()
