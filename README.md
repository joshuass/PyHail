# Python Hail Retrieval Toolkit (PyHail)

This toolkit provides a collection of hail retrieval techniques for
weather radar data built upon [Py-ART](https://github.com/ARM-DOE/pyart/)
and [col_processing](https://github.com/vlouf/cpol_processing). 

### Dependencies
- [Py-ART](https://github.com/ARM-DOE/pyart/)

### Hail Retrivals
- Hail Size Discrimination Algorithm - HSDA ([Ortega et al. 2016](https://journals.ametsoc.org/doi/10.1175/JAMC-D-15-0203.1))
- Hail Differential Reflectivity - HDR ([Depue et al. 2007](https://doi.org/10.1175/JAM2529.1))
- Maximum Expected Size of Hail - MESH ([Witt et al. 1998](https://journals.ametsoc.org/doi/10.1175/1520-0434%281998%29013%3C0286%3AAEHDAF%3E2.0.CO%3B2))

### Use
pipeline notebook: applies dual pol processing (filtering, attenuation corrections)
and hail retrievals to various radar formats (cfradial, odimh5, mdv). Note that radiosonde data must be supplied in netcdf format.
inspection_plot notebook: plots dual pol fields and all hail retrievals


