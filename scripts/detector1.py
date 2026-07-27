from jwst.pipeline import Detector1Pipeline

input_file = "/Users/gayathrykj/Downloads/CEERS/raw_uncal/jw01345062001_03201_00002_nrcb1_uncal.fits"

Detector1Pipeline.call(
    input_file,
    output_dir="/Users/gayathrykj/Downloads/CEERS/stage1_rate"
)