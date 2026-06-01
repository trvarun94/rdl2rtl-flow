// ============================================================
// GENERATED FILE — do not edit by hand.
// Source: spec/irq_ctrl.yaml
// Generator: tools/reggen/reggen_engine.py
//
// Block  : irq_ctrl
// Base   : 0x40001000
// Regs   : 5
//
// LEARNING NOTE: This is an APB (Advanced Peripheral Bus) register block.
// APB is the simplest AMBA bus — used for low-bandwidth control/status
// registers. The CPU writes/reads registers over APB; hardware logic
// uses the register values to control behavior.
//
// Access types in this block: rw, ro, wo, w1c, rclr
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
    // Hardware-interface ports (per access type)
    input  logic        hw_STATUS_BUSY,  // ro:  HW drives STATUS.BUSY (SW reads it)
    input  logic        hw_STATUS_IRQ,  // ro:  HW drives STATUS.IRQ (SW reads it)
    input  logic        hw_STATUS_ERR,  // ro:  HW drives STATUS.ERR (SW reads it)
    output logic        hw_TRIG_SOFT_IRQ,  // wo:  HW observes SW-written TRIG.SOFT_IRQ (SW readback is 0)
    output logic        hw_TRIG_SOFT_NMI,  // wo:  HW observes SW-written TRIG.SOFT_NMI (SW readback is 0)
    input  logic        hw_IRQ_STS_IRQ0_PEND_set,  // w1c: HW pulse to SET IRQ_STS.IRQ0_PEND (SW writes 1 to clear)
    input  logic        hw_IRQ_STS_IRQ1_PEND_set,  // w1c: HW pulse to SET IRQ_STS.IRQ1_PEND (SW writes 1 to clear)
    input  logic        hw_IRQ_STS_IRQ2_PEND_set,  // w1c: HW pulse to SET IRQ_STS.IRQ2_PEND (SW writes 1 to clear)
    input  logic [3:0] hw_FIFO_STS_EVT_COUNT,  // rclr:HW load value for FIFO_STS.EVT_COUNT
    input  logic        hw_FIFO_STS_EVT_COUNT_en  // rclr:HW load enable strobe (clears on SW read)
);

    // PREADY = 1: always respond in the access phase, no wait states.
    assign PREADY = 1'b1;

    // --------------------------------------------------------
    // Storage flip-flops — one per rw/wo/w1c/rclr field
    //   rw   : holds SW-written value (HW reads it)
    //   wo   : holds SW-written value (exposed as output port; readback=0)
    //   w1c  : sticky bit set by HW, cleared by SW write-1
    //   rclr : holds HW-loaded value; auto-clears on SW read
    // ro fields have NO flop — they are wires from the HW input port.
    // --------------------------------------------------------
    logic        r_CTRL_ENABLE;  // CTRL.ENABLE (1-bit rw)
    logic [1:0] r_CTRL_MODE;  // CTRL.MODE (2-bit rw)
    logic [2:0] r_CTRL_PRIORITY;  // CTRL.PRIORITY (3-bit rw)
    logic        r_IRQ_STS_IRQ0_PEND;  // IRQ_STS.IRQ0_PEND (1-bit w1c)
    logic        r_IRQ_STS_IRQ1_PEND;  // IRQ_STS.IRQ1_PEND (1-bit w1c)
    logic        r_IRQ_STS_IRQ2_PEND;  // IRQ_STS.IRQ2_PEND (1-bit w1c)
    logic        r_TRIG_SOFT_IRQ;  // TRIG.SOFT_IRQ (1-bit wo)
    logic        r_TRIG_SOFT_NMI;  // TRIG.SOFT_NMI (1-bit wo)
    logic [3:0] r_FIFO_STS_EVT_COUNT;  // FIFO_STS.EVT_COUNT (4-bit rclr)

    // wo fields: expose the SW-written value to HW via output port.
    // HW can detect a pulse on this signal to trigger an action.
    assign hw_TRIG_SOFT_IRQ = r_TRIG_SOFT_IRQ;
    assign hw_TRIG_SOFT_NMI = r_TRIG_SOFT_NMI;

    // --------------------------------------------------------
    // Sequential logic — all flop updates
    //
    // PRIORITY within one clock (last NBA assignment wins in always_ff):
    //   (1) APB write    — rw/wo store PWDATA; w1c write-1-clears
    //   (2) APB read     — rclr clears the flop                
    //   (3) HW _set      — w1c HW-set strobe (overrides SW ack)
    //   (4) HW _en       — rclr HW load     (overrides read-clear)
    // HW comes last → HW events never lost when racing with SW.
    // --------------------------------------------------------
    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            // Reset: drive every storable flop to its spec'd reset value
            r_CTRL_ENABLE <= 1'd0;
            r_CTRL_MODE <= 2'd0;
            r_CTRL_PRIORITY <= 3'd0;
            r_IRQ_STS_IRQ0_PEND <= 1'd0;
            r_IRQ_STS_IRQ1_PEND <= 1'd0;
            r_IRQ_STS_IRQ2_PEND <= 1'd0;
            r_TRIG_SOFT_IRQ <= 1'd0;
            r_TRIG_SOFT_NMI <= 1'd0;
            r_FIFO_STS_EVT_COUNT <= 4'd0;
        end else begin
            // (1) APB write phase ----------------------------------
            if (PSEL && PENABLE && PWRITE) begin
                case (PADDR[7:0])
                    8'h00: begin  // CTRL
                        r_CTRL_ENABLE <= PWDATA[0];  // rw: store PWDATA bits [0:0]
                        r_CTRL_MODE <= PWDATA[2:1];  // rw: store PWDATA bits [2:1]
                        r_CTRL_PRIORITY <= PWDATA[5:3];  // rw: store PWDATA bits [5:3]
                    end
                    8'h08: begin  // IRQ_STS
                        if (PWDATA[0]) r_IRQ_STS_IRQ0_PEND <= 1'b0;  // w1c: SW writes 1 → clear
                        if (PWDATA[1]) r_IRQ_STS_IRQ1_PEND <= 1'b0;  // w1c: SW writes 1 → clear
                        if (PWDATA[2]) r_IRQ_STS_IRQ2_PEND <= 1'b0;  // w1c: SW writes 1 → clear
                    end
                    8'h0C: begin  // TRIG
                        r_TRIG_SOFT_IRQ <= PWDATA[0];  // wo: store PWDATA bits [0:0]
                        r_TRIG_SOFT_NMI <= PWDATA[1];  // wo: store PWDATA bits [1:1]
                    end
                    default: ;  // unknown offset — write ignored
                endcase
            end
            // (2) APB read phase — rclr clears on read ------------
            // The clear is registered: it takes effect on the clock
            // edge AFTER the read, so the read still returns the old
            // value (via the combinational read mux below).
            if (PSEL && PENABLE && !PWRITE) begin
                case (PADDR[7:0])
                    8'h10: begin  // FIFO_STS
                        r_FIFO_STS_EVT_COUNT <= 4'd0;  // rclr: clear on read
                    end
                    default: ;
                endcase
            end
            // (3) HW _set strobes — w1c HW-set wins over SW ack
            if (hw_IRQ_STS_IRQ0_PEND_set) r_IRQ_STS_IRQ0_PEND <= 1'b1;  // HW sets IRQ_STS.IRQ0_PEND
            if (hw_IRQ_STS_IRQ1_PEND_set) r_IRQ_STS_IRQ1_PEND <= 1'b1;  // HW sets IRQ_STS.IRQ1_PEND
            if (hw_IRQ_STS_IRQ2_PEND_set) r_IRQ_STS_IRQ2_PEND <= 1'b1;  // HW sets IRQ_STS.IRQ2_PEND
            // (4) HW _en strobes — rclr HW load wins over read-clear
            if (hw_FIFO_STS_EVT_COUNT_en) r_FIFO_STS_EVT_COUNT <= hw_FIFO_STS_EVT_COUNT;  // HW loads FIFO_STS.EVT_COUNT
        end
    end

    // --------------------------------------------------------
    // Read mux — drive PRDATA based on PADDR (combinational).
    // Per-access readback rules:
    //   rw   → flop value
    //   ro   → live HW input port
    //   wo   → omitted from OR-tree (readback is 0)
    //   w1c  → flop value (sticky bit)
    //   rclr → flop value (clear happens next cycle in always_ff)
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
                8'h08: begin  // IRQ_STS
                    PRDATA = 32'(r_IRQ_STS_IRQ0_PEND) | (32'(r_IRQ_STS_IRQ1_PEND) << 1) | (32'(r_IRQ_STS_IRQ2_PEND) << 2);
                end
                8'h0C: begin  // TRIG
                    PRDATA = 32'h0;  // all fields are wo
                end
                8'h10: begin  // FIFO_STS
                    PRDATA = 32'(r_FIFO_STS_EVT_COUNT);
                end
                default: PRDATA = 32'h0;
            endcase
        end
    end

endmodule  // irq_ctrl
