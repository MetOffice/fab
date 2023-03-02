MODULE checks_and_balances_alg_mod
  USE constants_mod, ONLY: i_def, r_def
  USE log_mod, ONLY: log_event, LOG_LEVEL_INFO
  USE derived_config_mod, ONLY: bundle_size
  USE checks_config_mod, ONLY: limit_cfl, max_cfl
  USE field_mod, ONLY: field_type
  USE field_indices_mod, ONLY: igh_u
  USE limit_wind_kernel_mod, ONLY: limit_wind_kernel_type
  USE fem_constants_mod, ONLY: get_detJ_at_w2
  IMPLICIT NONE
  CONTAINS
  SUBROUTINE check_fields(state, dt)

  END SUBROUTINE check_fields
END MODULE checks_and_balances_alg_mod