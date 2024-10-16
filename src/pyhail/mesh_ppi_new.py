"""
MESH implementation for calculating on PPI data.
This algorthim was originally developed by Witt et al. 1998 and modified by Murillo and Homeyer 2019 

Joshua Soderholm - 15 August 2020
"""

import numpy as np
print('imports static in mesh')
import common

def main(
    reflectivity_dataset,
    elevation_dataset,
    azimuth_dataset,
    range_dataset,
    radar_altitude,
    levels,
    radar_band='S',
    min_range=10,
    max_range=150,
    mesh_method="mh2019_75",
    correct_cband_refl=True
):

    """
    Adapted from Witt et al. 1998 and Murillo and Homeyer 2019

    Parameters
    ----------
    reflectivity_dataset : list of 2D ndarrays
        list where each element is the sweep reflectivity data in an array with dimensions (azimuth, range)
    elevation_dataset: 1d ndarray of floats
        ndarray where each element is the fixed elevation angle of the sweep
    azimuth_dataset: list of 1D ndarrays
        list where each element is the sweep azimuth angles
    range_dataset: list of 1D ndarrays
        list where each element is the sweep range distances
    radar_altitude: float
        altitude of radar AMSL
    levels : list of length 2
        height above sea level (m) of the freezing level and -20C level (in any order)
    radar_band: str 
        radar frequency band (either C or S)
    min_range: int
        minimum surface range for MESH retrieval (m)
    max_range: int
        maximum surface range for MESH retrieval (m)
    mesh_method : string
        either witt1998, mh2019_75 or mh2019_95. see more information below
    correct_cband_refl: logical
        flag to trigger C band hail reflectivity correction (if radar_band is C)
    Returns
    -------
    output_fields : dictionary
        Dictionary of output fields (KE, SHI, MESH, POSH)
    """

    # require C or S band
    if radar_band not in ["C","S"]:
        raise ValueError("radar_band must be a string of value C or S")
    # require levels
    if levels is None:
        raise ValueError("Missing levels data for freezing level and -20C level")
    
    # Rain/Hail dBZ boundaries
    Zl = 40
    Zu = 50

    # This dummy proofs the user input. The melting level will always
    # be lower in elevation than the negative 20 deg C isotherm
    meltlayer = np.min(levels)
    neg20layer = np.max(levels)

    # sort by fixed angle
    sort_idx = list(np.argsort(elevation_dataset))
    reflectivity_dataset = [reflectivity_dataset[i] for i in sort_idx]
    elevation_dataset = [elevation_dataset[i] for i in sort_idx]
    azimuth_dataset = [azimuth_dataset[i] for i in sort_idx]
    range_dataset = [range_dataset[i] for i in sort_idx]
    n_ppi = len(elevation_dataset)

    # require more than one sweep
    if len(elevation_dataset) <= 1:
        raise Exception("Require more than one sweep to calculate MESH")
    elif len(elevation_dataset) < 10:
        raise Warning("Number of sweep is less than 10 and not recommended for MESH calculations")
    
    # Initialize sweeps
    x_dataset = []
    y_dataset = []
    z_dataset = []
    dz_dataset = []
    hail_ke_dataset = []
    SHI_elements_dataset = []
    valid_dataset = []
    hail_refl_correction_description = ''
    for i in range(n_ppi):
        #calculate cartesian coordinates
        elevation_array = np.zeros_like(range_dataset[i]) + elevation_dataset[i]
        range_grid, azimuth_grid = np.meshgrid(range_dataset[i], azimuth_dataset[i])
        range_grid, elevation_grid = np.meshgrid(range_dataset[i], elevation_array)
        
        x, y, z = common.antenna_to_cartesian(range_grid,
                                              azimuth_grid,
                                              elevation_grid)
        x_dataset.append(x)
        y_dataset.append(y)
        z_dataset.append(z + radar_altitude)
        # calculate shi ground range by ignoring Z
        ground_range = np.sqrt(x_dataset[0] ** 2 + y_dataset[0] ** 2)
        #apply C band correction
        if radar_band == 'C' and correct_cband_refl:
            reflectivity_dataset[i] = reflectivity_dataset[i] * 1.113 - 3.929
            hail_refl_correction_description = "C band hail reflectivity correction applied from Brook et al. 2023 https://arxiv.org/abs/2306.12016"
        #calculate dz for use in shi
        if i == 0:
            dz = z[i + 1, :, :] - z[i, :, :]
        if (i != 0) & (i != n_ppi - 1):
            dz = (z[i + 1, :, :] - z[i - 1, :, :]) / 2
        if i == n_ppi - 1:
            dz = z[i, :, :] - z[i - 1, :, :]
        dz_dataset.append(dz)
        # calc weights for hail kenetic energy
        reflectivity_weights = (reflectivity_dataset[i] - Zl) / (Zu - Zl)
        reflectivity_weights[reflectivity_dataset[i] <= Zl] = 0
        reflectivity_weights[reflectivity_dataset[i] >= Zu] = 1
        reflectivity_weights[reflectivity_weights < 0] = 0
        reflectivity_weights[reflectivity_weights > 1] = 1
        #limit on DBZ
        reflectivity_dataset[i][reflectivity_dataset[i] > 100] = 100
        reflectivity_dataset[i][reflectivity_dataset[i] < -100] = -100
        # calc hail kenetic energy
        hail_ke = (5.0e-6) * 10 ** (0.084 * reflectivity_dataset[i]) * reflectivity_weights
        hail_ke_dataset.append(hail_ke)
        # calc temperature based weighting function
        Wt = (z - meltlayer) / (neg20layer - meltlayer)
        Wt[z <= meltlayer] = 0
        Wt[z >= neg20layer] = 1
        Wt[Wt < 0] = 0
        Wt[Wt > 1] = 1
        # calc severe hail index (element wise for integration)
        SHI_elements = Wt * hail_ke * dz
        SHI_elements_dataset.append(SHI_elements)
        # calc valid mask
        valid = (
            (Wt > 0)
            & (hail_ke > 0)
            & (ground_range > min_range * 1000)
            & (ground_range < max_range * 1000)
        )
        valid_dataset.append(valid)

    #calculate shi on lowest sweep coordinates
    shi = np.zeros((len(azimuth_dataset[0]), len(range_dataset[0])))
    shi[:] = np.nan

    # loop through each ray in the lowest sweep
    for az_idx, az_value in range(azimuth_dataset[0]):
        # loop through each range bin for the ray
        for rg_idx, rg_value in range(range_dataset[0]):
            #init shi value
            if valid_dataset[0][az_idx, rg_idx]:
                shi_value = SHI_elements[0][az_idx, rg_idx]
            else:
                shi_value = 0
            #init x,y ground coods
            x_ground_coord = x_dataset[0][az_idx, rg_idx]
            y_ground_coord = y_dataset[0][az_idx, rg_idx]
            #loop through other sweeps above ground
            for sweep_idx in range(1, n_ppi, 1):
                # find closest point to ground location
                closest_idx = np.unravel_index(np.argmin((x_ground_coord-x_dataset[sweep_idx])**2 + (y_ground_coord-y_dataset[sweep_idx])**2),
                                               x_dataset[sweep_idx].shape)
                # skip invalid
                if not valid_dataset[sweep_idx][closest_idx]:
                    continue
                # skip empty values
                if SHI_elements_dataset[sweep_idx][closest_idx] == 0:
                    continue
                shi_value += SHI_elements_dataset[sweep_idx][closest_idx]
            # insert into SHI if there's a valid value
            if shi_value > 0:
                shi[az_idx, rg_idx] = 0.1 * shi

    # calc maximum estimated severe hail (mm)
    if (
        mesh_method == "witt1998"
    ):  # 75th percentil fit from witt et al. 1998 (fitted to 147 reports)
        mesh = 2.54 * shi ** 0.5
        mesh_description = "Maximum Estimated Size of Hail retreival developed by Witt et al. 1998 doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 "
        mesh_comment = "75th percentile fit using 147 hail reports; only valid in the first sweep"
        
    elif (
        mesh_method == "mh2019_75"
    ):  # 75th percentile fit from Muillo and Homeyer 2019 (fitted to 5897 reports)
        mesh = 15.096 * shi ** 0.206
        mesh_description = "Maximum Estimated Size of Hail retreival originally developed by Witt et al. 1998 doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 and recalibrated by Murillo and Homeyer (2021) doi:10.1175/JAMC-D-20-0271.1 "
        mesh_comment = "75th percentile fit using 5897 hail reports; only valid in the first sweep"
    elif (
        mesh_method == "mh2019_95"
    ):  # 95th percentile fit from Muillo and Homeyer 2019 (fitted to 5897 reports)
        mesh = 22.157 * shi ** 0.212
        mesh_description = "Maximum Estimated Size of Hail retreival originally developed by Witt et al. 1998 doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 and recalibrated by Murillo and Homeyer (2021) doi:10.1175/JAMC-D-20-0271.1 "
        mesh_comment = "95th percentile fit using 5897 hail reports; only valid in the first sweep"
    else:
        raise ValueError(
            "unknown MESH method selects, please use witt1998, mh2019_75 or mh2019_95"
        )

    # calc warning threshold (J/m/s) NOTE: freezing height must be in km
    WT = 57.5 * (meltlayer / 1000) - 121

    # calc probability of severe hail (POSH) (%)
    posh = 29 * common.safe_log(shi / WT) + 50
    posh = np.real(posh)
    posh[posh < 0] = 0
    posh[posh > 100] = 100

    
    # add grids to radar object
    # unpack E into cfradial representation
    ke_dict = {
        "data": hail_ke_dataset,
        "units": "Jm-2s-1",
        "long_name": "Hail Kinetic Energy",
        "description": "Hail Kinetic Energy developed by Witt et al. 1998 doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 " + 
        hail_refl_correction_description,
    }

    # SHI,MESH and POSH are only valid at the surface as a single sweep
    shi_dict = {
        "data": shi,
        "units": "Jm-1s-1",
        "long_name": "Severe Hail Index",
        "description": "Severe Hail Index developed by Witt et al. (1998) doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 " + 
        hail_refl_correction_description,
        "comments": "only valid in the first sweep",
    }

    mesh_dict = {
        "data": mesh,
        "units": "mm",
        "long_name": "Maximum Expected Size of Hail using " + mesh_method,
        "description":mesh_description + hail_refl_correction_description,
        "comments": mesh_comment,
    }
    
    posh_dict = {
        "data": posh,
        "units": "%",
        "long_name": "Probability of Severe Hail",
        "description": "Probability of Severe Hail developed by Witt et al. (1998) doi:10.1175/1520-0434(1998)013<0286:AEHDAF>2.0.CO;2 " +
        hail_refl_correction_description,
        "comments": "only valid in the first sweep",
    }
    
    # return output_fields dictionary
    return ke_dict, shi_dict, mesh_dict, posh_dict
