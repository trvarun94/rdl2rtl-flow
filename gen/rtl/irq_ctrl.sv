// ============================================================
// GENERATED FILE — do not edit by hand.
// Source: spec/irq_ctrl.yaml
// Generator: tools/reggen/reggen_engine.py
//
// Block  : irq_ctrl
// Base   : 0x40001000
// Regs   : 2
//
// LEARNING NOTE: This is an APB (Advanced Peripheral Bus) register block.
// APB is the simplest AMBA bus — used for low-bandwidth control/status
// registers. The CPU writes/reads registers over APB; hardware logic
// uses the register values to control behavior.
// ============================================================

`timescale 1ns/1ps

module irq_ctrl (
    // APB subordinate interface
    input  logic        PCLK,  // Clock — registers update on rising edge
    input  logic        PRESETn,  // Active-low reset — 0 means reset asserted
    input  logic [31:0] PADDR,  // Byte address from the APB manager (CPU)
    input  logic        PWRITE,  // 1 = write transaction, 0 = read transaction
    input  logic        PSEL,  // This block is selected
    input  logic        PENABLE,  // Second cycle of APB transfer (access phase)
    input  logic [31:0] PWDATA,  // Write data from the manager
    output logic [31:0] PRDATA,  // Read data back to the manager
    output logic        PREADY,  // We're ready (tied 1 = zero wait states)
    input  logic        hw_STATUS_BUSY,  // HW-driven: STATUS.BUSY
    input  logic        hw_STATUS_IRQ,  // HW-driven: STATUS.IRQ
    input  logic        hw_STATUS_ERR  // HW-driven: STATUS.ERR
);

    // PREADY = 1: always respond in the access phase, no wait states.
    assign PREADY = 1'b1;

    // --------------------------------------------------------
    // Storage flip-flops — one per rw field
    // Hold the value software last wrote. Hardware reads these
    // to know what software requested.
    // --------------------------------------------------------
    logic        r_CTRL_ENABLE;  // CTRL.ENABLE (1-bit rw)
    logic [1:0] r_CTRL_MODE;  // CTRL.MODE (2-bit rw)
    logic [2:0] r_CTRL_PRIORITY;  // CTRL.PRIORITY (3-bit rw)

    // --------------------------------------------------------
    // Write logic — triggered on APB write: PSEL & PENABLE & PWRITE
    // Decode PADDR[7:0] to find which register, then store PWDATA
    // bits into the matching field flip-flops.
    // --------------------------------------------------------
    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            // On reset: drive every rw field to its configured reset value
            r_CTRL_ENABLE <= 1'd0;
            r_CTRL_MODE <= 2'd0;
            r_CTRL_PRIORITY <= 3'd0;
        end else if (PSEL && PENABLE && PWRITE) begin
            // APB write: decode address offset, update matching fields.
            // PADDR[7:0] gives the register offset within this block.
            case (PADDR[7:0])
                8'h00: begin  // CTRL
                    r_CTRL_ENABLE <= PWDATA[0];  // ENABLE, bits [0:0]
                    r_CTRL_MODE <= PWDATA[2:1];  // MODE, bits [2:1]
                    r_CTRL_PRIORITY <= PWDATA[5:3];  // PRIORITY, bits [5:3]
                end
                default: ;  // write to unknown offset — silently ignored
            endcase
        end
    end

    // --------------------------------------------------------
    // Read mux — drive PRDATA based on PADDR (combinational)
    // Reconstruct the 32-bit register word by placing each field
    // at its correct bit position and OR-ing them together.
    // --------------------------------------------------------
    always_comb begin
        PRDATA = 32'h0;  // default: unimplemented addresses read as 0
        if (PSEL && !PWRITE) begin
            case (PADDR[7:0])
                8'h00: begin  // CTRL
                    PRDATA = 32'(r_CTRL_ENABLE) | (32'(r_CTRL_MODE) << 1) | (32'(r_CTRL_PRIORITY) << 3);
                end
                8'h04: begin  // STATUS
                    PRDATA = 32'(hw_STATUS_BUSY) | (32'(hw_STATUS_IRQ) << 1) | (32'(hw_STATUS_ERR) << 2);
                end
                default: PRDATA = 32'h0;
            endcase
        end
    end

endmodule  // irq_ctrl
