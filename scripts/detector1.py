from jwst.pipeline import Detector1Pipeline
import logging

logging.basicConfig(level=logging.DEBUG)

input_file = "/Users/gayathrykj/Downloads/CEERS/raw_uncal/jw01345062001_03201_00002_nrcalong_uncal.fits"

Detector1Pipeline.call(
    input_file,
    output_dir="/Users/gayathrykj/Downloads/CEERS/stage1_rate",
    save_results=True
)