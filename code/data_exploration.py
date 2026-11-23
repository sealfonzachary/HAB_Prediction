import glob
import xarray as xr

f = sorted(glob.glob("*.nc"))[0]

print("=" * 80)
print("FILE:")
print(f)

print("\nOPENING DATASET...\n")

ds = xr.open_dataset(f)

print(ds)

print("\n" + "=" * 80)
print("DIMENSIONS")
print(ds.dims)

print("\n" + "=" * 80)
print("COORDINATES")
for c in ds.coords:
    print(c, ds.coords[c].shape)

print("\n" + "=" * 80)
print("VARIABLES")
for v in ds.data_vars:
    print(v)

print("\n" + "=" * 80)
print("GLOBAL ATTRIBUTES")
for k, v in ds.attrs.items():
    print(f"{k}: {v}")

print("\n" + "=" * 80)
print("VARIABLE DETAILS")

for v in ds.data_vars:
    print("\n")
    print(v)
    print(ds[v])

    for a, val in ds[v].attrs.items():
        print(f"    {a}: {val}")

print("\n" + "=" * 80)