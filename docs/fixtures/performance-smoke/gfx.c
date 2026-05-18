static void program_gcvm_l2(void) {
  WREG32(mmGCVM_L2_CNTL, 1);
}

static void program_ih_ring(void) {
  WREG32(mmIH_RB_CNTL, 2);
}

static void program_sdma_queue(void) {
  WREG32(mmSDMA0_QUEUE0_RB_CNTL, 3);
}

static void program_cp_interrupt(void) {
  WREG32(mmCP_INT_CNTL_RING0, 4);
}
