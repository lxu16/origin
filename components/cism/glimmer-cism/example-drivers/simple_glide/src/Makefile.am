bin_PROGRAMS  =  simple_glide
if BUILD_EXT_EROSION
  bin_PROGRAMS += simple_erosion
endif

 
CLEANFILES = $(BUILT_SOURCES) f90_dep.mak $(wildcard *.mod)

lib_LTLIBRARIES = libglimmer-simple.la

libglimmer_simple_la_SOURCES = simple_forcing.F90 testsfg.F90
libglimmer_simple_la_LDFLAGS=-all-static

include $(top_builddir)/libglimmer-trilinos/Makefile.Trilinos.export
TRILINOS_LIBS =  $(TRILINOS_LIBS_ALL)

simple_glide_SOURCES = simple_glide.F90 trickLibtool.cpp
simple_glide_LDADD = libglimmer-simple.la $(top_builddir)/libglide/libglide.la $(top_builddir)/libglimmer-solve/libglimmer-solve.la \
                    $(top_builddir)/libglimmer/libglimmer-IO.la $(top_builddir)/libglimmer/libglimmer.la \
                    $(NETCDF_LDFLAGS) $(HDF5_LDFLAGS) $(NETCDF_LIBS) $(BLAS_LIBS) $(LAPACK_LIBS) \
                    $(PARDISO_LIBS) $(UMFPACK_LIBS)  $(TRILINOS_LIBS) $(FCLIBS) $(FLIBS)
# NOTE: On above line, FCLIBS and FLIBS are mostly redundant. Depending on
# the libtool version, there might not be FCLIBS, so FLIBS will fill in.

simple_erosion_SOURCES = simple_erosion.F90 trickLibtool.cpp
simple_erosion_LDADD = libglimmer-simple.la  $(top_builddir)/extensions/erosion/src/liberosion.la $(top_builddir)/libglide/libglide.la \
                    $(top_builddir)/libglimmer-solve/libglimmer-solve.la $(top_builddir)/libglimmer/libglimmer-IO.la $(top_builddir)/libglimmer/libglimmer.la \
                    $(NETCDF_LDFLAGS) $(HDF5_LDFLAGS) $(NETCDF_LIBS) $(BLAS_LIBS) $(TRILINOS_LIBS) $(FCLIBS) $(FLIBS)

AM_FCFLAGS = $(NETCDF_FCFLAGS) $(FC_MODINC)$(top_builddir)/libglimmer-solve $(FC_MODINC)$(top_builddir)/libglide $(FC_MODINC)$(top_builddir)/libglimmer \
             $(FC_MODINC)$(top_builddir)/extensions/erosion/src/

simple_glide.o : libglimmer-simple.la
simple_erosion.o : libglimmer-simple.la

-include f90_dep.mak
include $(top_srcdir)/extra_rules.am
