from astropy.io import fits
import matplotlib.pyplot as plt

filename = "/Users/gayathrykj/Downloads/CEERS/raw_uncal/jw01345062001_03201_00002_nrcalong_uncal.fits"

hdul = fits.open(filename)

# Verify the file
hdul.info()
print("Shape:", hdul[1].data.shape)

# Display the first group
image = hdul[1].data
plt.imshow(image[0, 0, :, :], origin="lower", cmap="gray")
plt.colorbar()
plt.title("JWST CEERS Raw Image")
plt.show()

hdul.close()