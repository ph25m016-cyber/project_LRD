from astropy.io import fits
import matplotlib.pyplot as plt
from astropy.visualization import ImageNormalize, PercentileInterval, AsinhStretch

fits_path = "calibrated/ceers_nircam1_f115w_single_i2d.fits"

image = fits.getdata(fits_path, "SCI")

normalization = ImageNormalize(
    image,
    interval=PercentileInterval(99.5),
    stretch=AsinhStretch(),
)

plt.figure(figsize=(14, 7))
plt.imshow(image, origin="lower", cmap="gray", norm=normalization)
plt.colorbar(label="MJy/sr")
plt.title("Stage 3 F115W mosaic")
plt.savefig("calibrated/f115w_mosaic_preview.png", dpi=150, bbox_inches="tight")
plt.show()