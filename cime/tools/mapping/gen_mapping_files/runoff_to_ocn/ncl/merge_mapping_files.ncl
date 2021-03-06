;
; merge_mapping_files.ncl
;
; merge two mapping files into one
;
; Keith Lindsay, 2017-03-08
; Mike Levy, 2017-03-23 (updated how arguments are passed to this script)
;
;   3 options for running this program:
;
;     1) use the ../run_merge_mapping_files.sh wrapper script
;        $ ../run_merge_mapping_files.sh --map_in_oo MAP_IN_OO_FNAME     \
;                                        --map_in_ms MAP_IN_MS_FNAME     \
;                                        --region_mask REGION_MASK_FNAME \
;                                        --map_out MAP_OUT_FNAME
;
;     2) ncl merge_mapping_files.ncl 'MAP_IN_OO_FNAME="file1_name"'   \
;                                    'MAP_IN_MS_FNAME="file2_name"'   \
;                                    'REGION_MASK_FNAME="file3_name"' \
;                                    'MAP_OUT_FNAME="file4_name"'
;
;     3) Set following environment variables:
;        MAP_IN_OO_FNAME (entries into the open ocean)
;        MAP_IN_MS_FNAME (entries into marginal seas)
;        REGION_MASK_FNAME (marginal seas designation)
;        MAP_OUT_FNAME (output file)
;

begin
  ; Initialize variables from command line or environment
  if (.not. isvar("MAP_IN_OO_FNAME")) then
     MAP_IN_OO_FNAME   = getenv("MAP_IN_OO_FNAME")
  end if

  if (.not. isvar("MAP_IN_MS_FNAME")) then
     MAP_IN_MS_FNAME   = getenv("MAP_IN_MS_FNAME")
  end if

  if (.not. isvar("REGION_MASK_FNAME")) then
     REGION_MASK_FNAME   = getenv("REGION_MASK_FNAME")
  end if

  if (.not. isvar("MAP_OUT_FNAME")) then
     MAP_OUT_FNAME   = getenv("MAP_OUT_FNAME")
  end if

  ; Make sure all input files exist
  missing_files = False
  if (.not. fileexists(MAP_IN_OO_FNAME)) then
    print((/"ERROR: can not find open ocean map ("+MAP_IN_OO_FNAME+ ")"/))
    missing_files = True
  end if
  if (.not. fileexists(MAP_IN_MS_FNAME)) then
    print((/"ERROR: can not find marginal sea map ("+MAP_IN_MS_FNAME+ ")"/))
    missing_files = True
  end if
  if (.not. fileexists(REGION_MASK_FNAME)) then
    print((/"ERROR: can not find region mask ("+REGION_MASK_FNAME+ ")"/))
    missing_files = True
  end if

  if (missing_files) then
    status_exit(1)
  end if

  map_in_oo_fp      = addfile(MAP_IN_OO_FNAME, "r")
  map_in_ms_fp      = addfile(MAP_IN_MS_FNAME, "r")

  ; ensure grid definitions in MAP_IN_MS_FNAME agrees with grid definitions in MAP_IN_MS_FNAME
  print("comparing grid vars in")
  print("  MAP_IN_OO_FNAME = " + MAP_IN_OO_FNAME)
  print("  MAP_IN_MS_FNAME = " + MAP_IN_MS_FNAME)
  grid_varnames = (/ "xc_a", "yc_a", "mask_a", "area_a", "frac_a", "src_grid_dims", \
                     "xc_b", "yc_b",           "area_b",           "dst_grid_dims" /)
  diffs_found = False
  do varind = 0, dimsizes(grid_varnames)-1
    varname = grid_varnames(varind)
    field_oo := map_in_oo_fp->$varname$
    field_ms := map_in_ms_fp->$varname$
    if (.not. all(ismissing(field_oo) .eq. ismissing(field_ms))) then
      print("  " + vars1(var_ind) + " _FillValue patterns differ")
      diffs_found = True
    end if
    if (all(field_oo .eq. field_ms)) then
      print("  " + varname + " values agree")
    else
      print("  " + varname + " values differ")
      if (any(abs(field_oo - field_ms) .gt. 1e-13 * (abs(field_oo)>abs(field_ms)))) then
        print("    differences appear to be greater than round-off")
        diffs_found = True
      else
        print("    differences appear to be less than round-off")
      end if
    end if
  end do
  if (.not. diffs_found) then
    print("grid variables are compatible")
  else
    status_exit(1)
  end if

  print("reading grid info and map from " + MAP_IN_OO_FNAME)
  xc_a          = map_in_oo_fp->xc_a
  yc_a          = map_in_oo_fp->yc_a
  xc_b          = map_in_oo_fp->xc_b
  yc_b          = map_in_oo_fp->yc_b
  dst_grid_dims = map_in_oo_fp->dst_grid_dims
  map_in_oo_S   = map_in_oo_fp->S
  map_in_oo_col = map_in_oo_fp->col ; 1-based indices
  map_in_oo_row = map_in_oo_fp->row ; 1-based indices
  n_s_oo        = dimsizes(map_in_oo_S)

  print("reading map from " + MAP_IN_MS_FNAME)
  map_in_ms_S   = map_in_ms_fp->S
  map_in_ms_col = map_in_ms_fp->col
  map_in_ms_row = map_in_ms_fp->row
  n_s_ms        = dimsizes(map_in_ms_S)

  ; ensure that maps have same unique col values, i.e., they are mapping from same src points
  print("checking col value compatibility")
  map_in_oo_col_unique = get_unique_values(map_in_oo_col)
  map_in_ms_col_unique = get_unique_values(map_in_ms_col)
  if (dimsizes(map_in_oo_col_unique) .ne. dimsizes(map_in_ms_col_unique)) then
    print("number of unique col values in " + MAP_IN_OO_FNAME + " and " + MAP_IN_MS_FNAME + " differ")
    status_exit(1)
  end if
  if (any(map_in_oo_col_unique .ne. map_in_ms_col_unique)) then
    print("unique col values in " + MAP_IN_OO_FNAME + " and " + MAP_IN_MS_FNAME + " differ")
    status_exit(1)
  end if

  ; load POP region mask from REGION_MASK_FNAME
  print("reading REGION_MASK")
  setfileoption("bin", "ReadByteOrder", "BigEndian")
  REGION_MASK = cbinread(REGION_MASK_FNAME, (/ dst_grid_dims(1), dst_grid_dims(0) /), "integer")
  REGION_MASK_1d = ndtooned(REGION_MASK)

  ; create merged mapping

  ; determine size of merged map

  print("determining map_oo vals where REGION_MASK>0")
  sign_REGION_MASK_oo = sign_matlab(REGION_MASK_1d(map_in_oo_row-1))
  ind_vals_oo = ind(sign_REGION_MASK_oo .gt. 0)
  n_s_subset_oo = dimsizes(ind_vals_oo)

  print("determining map_ms vals where REGION_MASK<0")
  sign_REGION_MASK_ms = sign_matlab(REGION_MASK_1d(map_in_ms_row-1))
  ind_vals_ms = ind(sign_REGION_MASK_ms .lt. 0)
  n_s_subset_ms = dimsizes(ind_vals_ms)

  n_s_out = n_s_subset_oo + n_s_subset_ms

  ; allocate output vars

  map_out_S = new(n_s_out, double)
  map_out_S!0 = "n_s"
  delete(map_out_S@_FillValue)
  map_out_S@long_name = map_in_ms_S@long_name

  map_out_col = new(n_s_out, integer)
  map_out_col!0 = "n_s"
  delete(map_out_col@_FillValue)
  map_out_col@long_name = map_in_ms_col@long_name

  map_out_row = new(n_s_out, integer)
  map_out_row!0 = "n_s"
  delete(map_out_row@_FillValue)
  map_out_row@long_name = map_in_ms_row@long_name

  ; fill output vars

  map_out_S(0:n_s_subset_oo-1)   = (/ map_in_oo_S(ind_vals_oo) /)
  map_out_col(0:n_s_subset_oo-1) = (/ map_in_oo_col(ind_vals_oo) /)
  map_out_row(0:n_s_subset_oo-1) = (/ map_in_oo_row(ind_vals_oo) /)

  map_out_S(n_s_subset_oo:n_s_subset_oo+n_s_subset_ms-1)   = (/ map_in_ms_S(ind_vals_ms) /)
  map_out_col(n_s_subset_oo:n_s_subset_oo+n_s_subset_ms-1) = (/ map_in_ms_col(ind_vals_ms) /)
  map_out_row(n_s_subset_oo:n_s_subset_oo+n_s_subset_ms-1) = (/ map_in_ms_row(ind_vals_ms) /)

  print("writing merged map, " + MAP_OUT_FNAME)
  system("rm -f " + MAP_OUT_FNAME)
  map_out_fp = addfile(MAP_OUT_FNAME, "c")

  map_out_fp@history = "File created: "+systemfunc("date +%Y-%m-%d\ %H:%M:%S")
  map_out_fp@conventions = "NCAR-CCSM"
  map_out_fp@open_ocean_mapping_fname = MAP_IN_OO_FNAME
  map_out_fp@marginal_seas_mapping_fname = MAP_IN_MS_FNAME
  map_out_fp@region_mask_fname = REGION_MASK_FNAME

  copy_varnames = (/ "xc_a", "yc_a", "xv_a", "yv_a", "mask_a", "area_a", "frac_a", "src_grid_dims", \
                     "xc_b", "yc_b", "xv_b", "yv_b", "mask_b", "area_b", "frac_b", "dst_grid_dims" /)

  do varind = 0, dimsizes(copy_varnames)-1
    varname = copy_varnames(varind)
    map_out_fp->$varname$ = map_in_ms_fp->$varname$
  end do

  ; read mask from map_ms (for size and metadata)
  ; set it to 1 where merged mapping maps to
  mask_b = map_in_ms_fp->mask_b
  mask_b = 0
  mask_b(map_out_row-1) = 1
  map_out_fp->mask_b = (/ mask_b /)

  filedimdef(map_out_fp, "n_s", n_s_out, False)
  map_out_fp->S   = map_out_S(0:n_s_out-1)
  map_out_fp->col = map_out_col(0:n_s_out-1)
  map_out_fp->row = map_out_row(0:n_s_out-1)
end
