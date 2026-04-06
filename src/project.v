`default_nettype none

module tt_um_AnjaniKad_medical_bms (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    wire [3:0] voltage    = ui_in[3:0];
    wire [1:0] current    = ui_in[5:4];
    wire       temp_flag  = ui_in[6];
    wire       safe_reset = ui_in[7];

    wire volt_valid = (voltage != 4'd0);
    wire volt_crit  = volt_valid & ((voltage == 4'd1) | (voltage >= 4'd14));
    wire volt_warn   = ((voltage == 4'd2)  | (voltage == 4'd3) |
                        (voltage == 4'd12) | (voltage == 4'd13));
    wire volt_normal = ~volt_crit & ~volt_warn;

    reg [1:0] soc;
    always @(*) begin
        if      (voltage <= 4'd1)  soc = 2'b00;
        else if (voltage <= 4'd4)  soc = 2'b01;
        else if (voltage <= 4'd10) soc = 2'b10;
        else                       soc = 2'b11;
    end

    wire curr_warn = (current == 2'b01);
    wire curr_crit = current[1];

    reg thermal_latch;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            thermal_latch <= 1'b0;
        else if (temp_flag)
            thermal_latch <= 1'b1;
        else if (safe_reset && !temp_flag)
            thermal_latch <= 1'b0;
    end

    wire any_crit = volt_crit | curr_crit | thermal_latch;
    wire any_warn = volt_warn | curr_warn;
    wire all_safe = volt_normal & ~curr_crit & ~curr_warn & ~thermal_latch;

    localparam IDLE     = 2'b00;
    localparam WARN     = 2'b01;
    localparam FAULT    = 2'b10;
    localparam SHUTDOWN = 2'b11;

    reg [1:0] state, next_state;

    reg [2:0] hyst_cnt;
    wire      hyst_done = (hyst_cnt == 3'd7);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            hyst_cnt <= 3'd0;
        else if ((state == WARN) && all_safe)
            hyst_cnt <= hyst_cnt + 3'd1;
        else
            hyst_cnt <= 3'd0;
    end

    reg [3:0] wdog_cnt;
    wire      wdog_fired = (wdog_cnt == 4'd15);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            wdog_cnt <= 4'd0;
        else if (state == FAULT)
            wdog_cnt <= wdog_fired ? wdog_cnt : (wdog_cnt + 4'd1);
        else
            wdog_cnt <= 4'd0;
    end

    // FSM with ena (TT compliant)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else if (ena) state <= next_state;
    end

    always @(*) begin
        case (state)
            IDLE: begin
                if      (any_crit)              next_state = FAULT;
                else if (any_warn)              next_state = WARN;
                else                            next_state = IDLE;
            end
            WARN: begin
                if      (any_crit)              next_state = FAULT;
                else if (hyst_done && all_safe) next_state = IDLE;
                else                            next_state = WARN;
            end
            FAULT: begin
                if      (wdog_fired)            next_state = SHUTDOWN;
                else if (safe_reset && all_safe) next_state = IDLE;
                else                            next_state = FAULT;
            end
            SHUTDOWN: begin
                if (safe_reset && all_safe)     next_state = IDLE;
                else                            next_state = SHUTDOWN;
            end
            default:                            next_state = IDLE;
        endcase
    end

    // ORIGINAL OUTPUTS (kept for meaning)
    wire [7:0] core_out;
    assign core_out[0]   = (state != IDLE);
    assign core_out[1]   = (state == SHUTDOWN);
    assign core_out[2]   = thermal_latch;
    assign core_out[4:3] = state;
    assign core_out[6:5] = soc;
    assign core_out[7]   = curr_crit;

    // DISPLAY LOGIC (IMPROVED)
    wire [3:0] display_val;
    assign display_val = {state, soc};  // 0–15 range

    reg [6:0] seg;

    always @(*) begin
        case (display_val)
            4'd0: seg = 7'b0111111;
            4'd1: seg = 7'b0000110;
            4'd2: seg = 7'b1011011;
            4'd3: seg = 7'b1001111;
            4'd4: seg = 7'b1100110;
            4'd5: seg = 7'b1101101;
            4'd6: seg = 7'b1111101;
            4'd7: seg = 7'b0000111;
            4'd8: seg = 7'b1111111;
            4'd9: seg = 7'b1101111;
            4'd10: seg = 7'b1110111; // A
            4'd11: seg = 7'b1111100; // b
            4'd12: seg = 7'b0111001; // C
            4'd13: seg = 7'b1011110; // d
            4'd14: seg = 7'b1111001; // E
            4'd15: seg = 7'b1110001; // F
            default: seg = 7'b0000000;
        endcase
    end

    // FINAL OUTPUT
    assign uo_out = core_out;

endmodule
