# CMake initial cache file for babbage host 
SET (CMAKE_Fortran_COMPILER mpiifort CACHE FILEPATH "")
SET (CMAKE_C_COMPILER mpiicc CACHE FILEPATH "")
SET (CMAKE_CXX_COMPILER mpiicpc CACHE FILEPATH "")
SET (NETCDF_DIR $ENV{NETCDF_DIR} CACHE FILEPATH "")
SET (WITH_PNETCDF FALSE CACHE BOOL "")
SET (HDF5_DIR $ENV{HDF5_DIR} CACHE FILEPATH "")

