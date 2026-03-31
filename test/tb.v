`default_nettype none
`timescale 1ns / 1ps

module tb ();

  initial begin
    $display("=== Medical Battery Monitor — TinyTapeout Testbench ===");
    $dumpfile("tb.fst");
    $dumpvars(0, tb);
    #1;
  end

  reg clk;
  reg rst_n;
  reg ena;
  reg  [7:0] ui_in;
  reg  [7:0] uio_in;
  wire [7:0] uo_out;
  wire [7:0] uio_out;
  wire [7:0] uio_oe;

`ifdef GL_TEST
  wire VPWR = 1'b1;
  wire VGND = 1'b0;
`endif

  // FIXED MODULE NAME
  tt_um_AnjaniKad_medical_bms user_project (
`ifdef GL_TEST
      .VPWR   (VPWR),
      .VGND   (VGND),
`endif
      .ui_in  (ui_in),
      .uo_out (uo_out),
      .uio_in (uio_in),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (ena),
      .clk    (clk),
      .rst_n  (rst_n)
  );

  // INIT
  initial begin
    clk = 0;
    rst_n = 0;
    ena = 1;
    ui_in = 0;
    uio_in = 0;
  end

  // CLOCK
  always #5 clk = ~clk;

  // TEST SEQUENCE
  initial begin
    #10 rst_n = 1;

    ui_in = 8'b01000000;
    #50;

    ui_in = 8'b00000010;
    #50;

    ui_in = 8'b01000000 | (1 << 6);
    #50;

    ui_in[7] = 1;
    #50;

    $finish;
  end

endmodule
