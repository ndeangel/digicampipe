#!/usr/bin/env bash

export FMPE_CHARGE_HISTO=$DIGICAM_FOLDER'fmpe_charge_histo.fits'
export FMPE_AMPLITUDE_HISTO=$DIGICAM_FOLDER'fmpe_amplitude_histo.fits'
export FMPE_RESULTS=$DIGICAM_FOLDER'fmpe_results.fits'

digicam-fmpe --compute --charge_histo_filename=$FMPE_CHARGE_HISTO --amplitude_histo_filename=$FMPE_AMPLITUDE_HISTO --results_filename=$FMPE_RESULTS --pixels=$(tolist "${DIGICAM_PIXELS[@]}") --output=$fmpe_folder --estimated_gain=$DIGICAM_GAIN_APPROX --n_samples=$DIGICAM_N_SAMPLES --shift=DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS ${DIGICAM_AC_FILES[@]}
digicam-fmpe --fit --charge_histo_filename=$FMPE_CHARGE_HISTO --amplitude_histo_filename=$FMPE_AMPLITUDE_HISTO --results_filename=$FMPE_RESULTS --pixels=$(tolist "${DIGICAM_PIXELS[@]}") --output=$fmpe_folder --estimated_gain=$DIGICAM_GAIN_APPROX --n_samples=$DIGICAM_N_SAMPLES --shift=DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS ${DIGICAM_AC_FILES[@]}
# digicam-fmpe --save_figures --charge_histo_filename=$FMPE_CHARGE_HISTO --amplitude_histo_filename=$FMPE_AMPLITUDE_HISTO --results_filename=$FMPE_RESULTS --pixels=$(tolist "${DIGICAM_PIXELS[@]}") --output=$fmpe_folder --estimated_gain=$DIGICAM_GAIN_APPROX --n_samples=$DIGICAM_N_SAMPLES --shift=DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS ${DIGICAM_AC_FILES[@]}
# digicam-fmpe --display --charge_histo_filename=$FMPE_CHARGE_HISTO --amplitude_histo_filename=$FMPE_AMPLITUDE_HISTO --results_filename=$FMPE_RESULTS --pixels=$(tolist "${DIGICAM_PIXELS[@]}") --output=$fmpe_folder --estimated_gain=$DIGICAM_GAIN_APPROX --n_samples=$DIGICAM_N_SAMPLES --shift=DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS ${DIGICAM_AC_FILES[@]}