from astropy.utils.data import download_file
from astropy.io import fits

# Download FITS file
image_file = download_file(
    "http://data.astropy.org/tutorials/FITS-images/HorseHead.fits",
    cache=True
)

# Open FITS file
hdul = fits.open(image_file)

# Read header
header = hdul[0].header

# Print complete header
print("Object :", header["OBJECT"])
print("Date   :", header["DATE"])
print("Telescope :", header["TELESCOP"])
print("Instrument :", header["INSTRUME"])
image = hdul[0].data
print(image.shape)


hdul.close()