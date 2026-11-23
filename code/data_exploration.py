import glob
import xarray as xr

files = sorted(glob.glob(
    "/glade/derecho/scratch/zacharys/HAB_Prediction/data/modis/*.nc"
))

print(f"Found {len(files)} files")

f = files[0]

print("\nFILE:")
print(f)

ds = xr.open_dataset(f)

print("\nDATASET:")
print(ds)

print("\nVARIABLES:")
for v in ds.data_vars:
    print(f"\n{'='*60}")
    print(v)
    print(ds[v])

print("\nCOORDINATES:")
for c in ds.coords:
    print(c)

print("\nDIMENSIONS:")
print(ds.dims)

print("\nATTRIBUTES:")
for k, v in ds.attrs.items():
    print(f"{k}: {v}")