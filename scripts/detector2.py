from jwst.pipeline import Image2Pipeline

input_file = "/Users/gayathrykj/Downloads/CEERS/stage1_rate/jw01345062001_03201_00002_nrcalong_rate.fits"

Image2Pipeline.call(
    input_file,
    output_dir="/Users/gayathrykj/Downloads/CEERS/stage2_cal",
    save_results=True
)