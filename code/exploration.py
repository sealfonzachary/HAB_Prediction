
import os
import glob
import xarray as xr

data_dir = "/glade/derecho/scratch/zacharys/MODISA_L3m_CHL_2022.0-20260930_155709"

files = sorted(glob.glob(f"{data_dir}/*.nc"))

print("Number of files:", len(files))
print("First 5 files:")

for f in files[:5]:
    print(os.path.basename(f))

# Open first file
file = files[0]

with xr.open_dataset(file) as ds:
    print("\nFILE:", os.path.basename(file))
    print(ds)

    print("\nVARIABLES:")
    print(list(ds.data_vars))

    print("\nCOORDINATES:")
    print(list(ds.coords))

    print("\nDIMENSIONS:")
    print(ds.sizes)