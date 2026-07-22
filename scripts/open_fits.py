from astropy.utils.data import download_file
from astropy.io import fits
import matplotlib.pyplot as plt

# Download the FITS file
image_file = download_file(
    "http://data.astropy.org/tutorials/FITS-images/HorseHead.fits",
    cache=True
)

# Open the FITS file
hdul = fits.open(image_file)

# Show FITS information
hdul.info()

# Read image data
image = hdul[0].data

# Display the image
plt.imshow(image, cmap="gray", origin="lower")
plt.colorbar()
plt.title("Horsehead Nebula")
plt.show()

# Close the file
hdul.close()
