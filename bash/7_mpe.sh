#!/usr/bin/env bash
#SBATCH --time=02:00:00
#SBATCH --partition=shared
#SBATCH --mem=4G
#SBATCH --output=/home/%u/job_logs/%x-%A_%a.out
#SBATCH --job-name='mpe'

source 0_main.sh ${SLURM_ARRAY_TASK_ID}

PIXEL=${DIGICAM_PIXELS[0]}

output=$DIGICAM_FOLDER'mpe_combined_fit_results_'$PIXEL'.fits'
rm $output
# digicam-mpe --compute --ac_led_filename=$AC_LED_FILE --compute_output=$MPE_CHARGE_HISTO --fit_output=$MPE_RESULTS --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}
# digicam-mpe --fit --ac_led_filename=$AC_LED_FILE --compute_output=$MPE_CHARGE_HISTO --fit_output=$MPE_RESULTS --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}
digicam-mpe --fit_summed --ac_led_filename=$AC_LED_FILE --compute_output=$MPE_CHARGE_HISTO --fit_output=$output --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}
digicam-mpe --fit_combine --ac_led_filename=$AC_LED_FILE --compute_output=$MPE_CHARGE_HISTO --fit_output=$output --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}
digicam-mpe --figure_path=$DIGICAM_FOLDER'figures/mpe_fit_combined_'$PIXEL'.pdf' --ac_led_filename=$AC_LED_FILE --compute_output=$MPE_CHARGE_HISTO --fit_output=$output --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}
# digicam-mpe --display --compute_output=$MPE_CHARGE_HISTO --fit_output=$MPE_RESULTS --shift=$DIGICAM_INTEGRAL_SHIFT --integral_width=$DIGICAM_INTEGRAL_WIDTH --timing=$TIMING_RESULTS --gain=$FMPE_RESULTS --adc_min=$DIGICAM_LSB_MIN --adc_max=$DIGICAM_LSB_MAX --pixel=$(tolist "${DIGICAM_PIXELS[@]}") --ac_levels=$(tolist "${DIGICAM_AC_LEVEL[@]}") ${DIGICAM_AC_FILES[@]}