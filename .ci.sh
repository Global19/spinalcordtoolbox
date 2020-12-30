#!/usr/bin/env bash
# CI testing script
#  Installs SCT from scratch and runs all the tests we've ever written for it.

# stricter shell mode
# https://sipb.mit.edu/doc/safe-shell/
set -eo pipefail  # exit if non-zero error is encountered (even in a pipeline)
set -u            # exit if unset variables used
shopt -s failglob # error if a glob doesn't find any files, instead of remaining unexpanded

export PIP_PROGRESS_BAR=off # disable pip's progress bar for the duration of CI

echo Installing SCT
./install_sct -iy
. ~/.bash_profile # load sct

echo *** CHECK PATH ***
# Make sure all binaries and aliases are there
for tool in \
            isct_antsApplyTransforms \
            isct_antsRegistration \
            isct_antsSliceRegularizedRegistration \
            isct_ComposeMultiTransform \
            isct_convert_binary_to_trilinear \
            isct_dice_coefficient \
            isct_minc2volume-viewer \
            isct_propseg \
            isct_spine_detect \
            isct_test_ants \
            isct_train_svm \
            sct_analyze_lesion \
            sct_analyze_texture \
            sct_apply_transfo \
            sct_check_dependencies \
            sct_compute_ernst_angle \
            sct_compute_hausdorff_distance \
            sct_compute_mscc \
            sct_compute_mtr \
            sct_compute_mtsat \
            sct_compute_snr \
            sct_convert \
            sct_create_mask \
            sct_crop_image \
            sct_deepseg \
            sct_deepseg_gm \
            sct_deepseg_lesion \
            sct_deepseg_sc \
            sct_denoising_onlm \
            sct_detect_pmj \
            sct_dice_coefficient \
            sct_dmri_compute_bvalue \
            sct_dmri_compute_dti \
            sct_dmri_concat_b0_and_dwi \
            sct_dmri_concat_bvals \
            sct_dmri_concat_bvecs \
            sct_dmri_display_bvecs \
            sct_dmri_moco \
            sct_dmri_separate_b0_and_dwi \
            sct_dmri_transpose_bvecs \
            sct_download_data \
            sct_extract_metric \
            sct_flatten_sagittal \
            sct_fmri_compute_tsnr \
            sct_fmri_moco \
            sct_get_centerline \
            sct_image \
            sct_label_utils \
            sct_label_vertebrae \
            sct_maths \
            sct_merge_images \
            sct_process_segmentation \
            sct_propseg \
            sct_qc \
            sct_register_multimodal \
            sct_register_to_template \
            sct_resample \
            sct_run_batch \
            sct_smooth_spinalcord \
            sct_straighten_spinalcord \
            sct_testing \
            sct_version \
            sct_warp_template; \
            do
  command -v "$tool" || (echo "Missing tool: $tool"; exit 1)
done

source "$SCT_DIR/python/etc/profile.d/conda.sh"  # to be able to call conda
conda activate venv_sct  # reactivate conda for the pip install below

echo *** UNIT TESTS ***
pip install coverage
echo -ne "import coverage\ncov = coverage.process_startup()\n" > sitecustomize.py
echo -ne "[run]\nconcurrency = multiprocessing\nparallel = True\n" > .coveragerc
COVERAGE_PROCESS_START="$PWD/.coveragerc" COVERAGE_FILE="$PWD/.coverage" \
  pytest
coverage combine

# TODO: move this part to a separate travis job; there's no need for each platform to lint the code
echo *** ANALYZE CODE ***
pip install pylint
bash -c 'PYTHONPATH="$PWD/scripts:$PWD" pylint -j3 --py3k --output-format=parseable --errors-only $(git ls-tree --name-only -r HEAD | sort | grep -E "(spinalcordtoolbox|scripts|testing).*\.py" | xargs); exit $(((($?&3))!=0))'

# python create_package.py -s ${TRAVIS_OS_NAME}  # test package creation
# cd ../spinalcordtoolbox_v*
# yes | ./install_sct  # test installation of package
