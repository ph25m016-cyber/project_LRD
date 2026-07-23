from astropy.utils.data import download_file
from astropy.io import fits
import matplotlib.pyplot as plt
import numpy as np

# Download FITS file
image_file = download_file(
    "http://data.astropy.org/tutorials/FITS-images/HorseHead.fits",
    cache=True
)

# Open FITS file
hdul = fits.open(image_file)
image = hdul[0].data

# Find brightest pixel
row, col = np.unravel_index(np.argmax(image), image.shape)

print("Row:", row)
print("Column:", col)
print("Brightness:", image[row, col])

# Display image
plt.figure(figsize=(8, 8))
plt.imshow(image, cmap="gray", origin="lower")

# Mark brightest pixel
plt.scatter(col, row, color="red", s=120, marker="o", facecolors="none")

plt.title("Brightest Pixel in Horsehead Nebula")
plt.show()


hdul.close()