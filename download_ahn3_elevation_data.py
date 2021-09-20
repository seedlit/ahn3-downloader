# this script finds all the intersecting tiles for a given input AOI, and then downloads corresponding
# 0.5 meter AHN3 DSM and DTM tiles


from shapely.geometry import Polygon
import geopandas as gpd
import pandas as pd
from tqdm import tqdm
from multiprocessing import Pool
import urllib.request
import zipfile
import os
import argparse


def get_intersecting_tile_names(bounds_csv_path, aoi_path):
    print("Finding all the intersecting tile names")
    # all the tile bounds are in EPSG 28992
    # reproject the aoi bounds to EPSG 28992
    # define aoi bounds
    aoi_df = gpd.read_file(aoi_path)
    if aoi_df.crs != 28992:
        aoi_df = aoi_df.to_crs(epsg=28992)
    tile_names_list = []
    # read csv into dataframe
    tiles_bounds_df = pd.read_csv(bounds_csv_path)
    for i in tqdm(range(len(tiles_bounds_df))):
        tile_name = tiles_bounds_df["tile_name"].iloc[i]
        tile_left = tiles_bounds_df["left"].iloc[i]
        tile_right = tiles_bounds_df["right"].iloc[i]
        tile_bottom = tiles_bounds_df["bottom"].iloc[i]
        tile_top = tiles_bounds_df["top"].iloc[i]
        # generate shapely geometry
        tile_poly = gpd.GeoSeries(
            [
                Polygon(
                    [
                        (tile_left, tile_bottom),
                        (tile_right, tile_bottom),
                        (tile_right, tile_top),
                        (tile_left, tile_top),
                    ]
                )
            ]
        )
        tile_df = gpd.GeoDataFrame(
            {"geometry": tile_poly, "df1": [1]}, crs="EPSG:28992"
        )
        if aoi_df.intersects(tile_df).any():
            tile_names_list.append(tile_name)
    print("the intersecting tiles are ", tile_names_list)
    return tile_names_list


def download_data(download_url, out_path):
    urllib.request.urlretrieve(download_url, out_path)


def extract_zip(src_zip_file, out_dir):
    zip_name = src_zip_file.split("/")[-1].replace(".zip", "")
    zip_data = zipfile.ZipFile(src_zip_file)
    zipinfos = zip_data.infolist()
    # iterate through each file    
    os.chdir(out_dir)
    for zipinfo in zipinfos:
        # Rename the zip content
        zipinfo.filename = "{}.tif".format(zip_name)
        zip_data.extract(zipinfo)
    os.remove(os.path.join(os.path.join(os.getcwd(), "{}.zip".format(zip_name))))
    return os.path.join(out_dir, "{}.tif".format(zip_name))


def download_and_extract(tile_name, out_dir, download_url):
    try:
        out_path = os.path.join(out_dir, "{}.zip".format(tile_name))
        download_data(download_url, out_path)
        tif_path = extract_zip(out_path, out_dir)
        # return tif_path
    except Exception as e:
        print("some error in ", tile_name)
        print("error ", e)


def download_tiles_multiprocess(tile_names_list, out_dir, num_processes):
    download_task_list = []
    dsm_dir = os.path.join(out_dir, "dsm")
    os.makedirs(dsm_dir, exist_ok=True)
    dtm_dir = os.path.join(out_dir, "dtm")
    os.makedirs(dtm_dir, exist_ok=True)
    for tile_name in tile_names_list:
        dsm_url = "https://download.pdok.nl/rws/ahn3/v1_0/05m_dsm/R_{}.ZIP".format(
            tile_name
        )
        dtm_url = "https://download.pdok.nl/rws/ahn3/v1_0/05m_dtm/M_{}.ZIP".format(
            tile_name
        )
        download_task_list.append([tile_name, dsm_dir, dsm_url])
        download_task_list.append([tile_name, dtm_dir, dtm_url])
    print("Dowloding {} tiles".format(len(download_task_list)))
    p = Pool(num_processes)
    p.starmap(download_and_extract, download_task_list)
    p.close()
    p.join()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Download AHN3 DSM and DTM tiles for input AOI"
    )
    parser.add_argument("--aoi", help="aoi geojson/shpefile path string")
    parser.add_argument(
        "--out_dir",
        help="path to out directory where files will be downloaded",
        type=str,
        default="downloaded_tiles",
    )
    parser.add_argument(
        "--num_processes",
        help="Number of processes to run in parallel, to speed up downloading",
        type=int,
        default=10,
    )

    args = parser.parse_args()
    aoi_path = args.aoi
    out_dir = args.out_dir
    num_processes = args.num_processes

    os.makedirs(out_dir, exist_ok=True)
    bounds_csv_path = "resources/ahn3_tile_bounds.csv"

    target_tile_names = get_intersecting_tile_names(bounds_csv_path, aoi_path)
    download_tiles_multiprocess(target_tile_names, out_dir, num_processes)
    print("Data downloaded at ", os.path.join(os.getcwd(), out_dir))
