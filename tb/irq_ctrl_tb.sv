// ============================================================
// Testbench: irq_ctrl_tb
// DUT:       gen/rtl/irq_ctrl.sv  (APB register block, 5 regs)
//
// Purpose: self-checking functional verification of every access
// type the register generator can produce: rw, ro, wo, w1c, rclr.
//
// Simulator: iverilog -g2012
// Run:       vvp gen/sim/irq_ctrl_sim
//
// LEARNING NOTE — what a testbench does:
//   The DUT (Device Under Test) is the generated RTL module.
//   The testbench is a non-synthesisable wrapper that:
//     1. Instantiates the DUT
//     2. Drives stimulus (APB transactions, HW port pulses)
//     3. Checks responses ($fatal on mismatch → non-zero exit → Make fails)
//   It is the functional equivalent of a unit test for RTL.
// ============================================================

`timescale 1ns/1ps

module irq_ctrl_tb;

    // --------------------------------------------------------
    // Signal declarations — mirror every DUT port
    // --------------------------------------------------------

    // APB manager-side signals (testbench drives these)
    logic        PCLK;
    logic        PRESETn;
    logic [31:0] PADDR;
    logic        PWRITE;
    logic        PSEL;
    logic        PENABLE;
    logic [31:0] PWDATA;

    // APB subordinate-side signals (DUT drives these)
    logic [31:0] PRDATA;
    logic        PREADY;

    // Hardware interface — ro inputs (testbench drives, DUT reads)
    logic        hw_STATUS_BUSY;
    logic        hw_STATUS_IRQ;
    logic        hw_STATUS_ERR;

    // Hardware interface — wo outputs (DUT drives, testbench observes)
    logic        hw_TRIG_SOFT_IRQ;
    logic        hw_TRIG_SOFT_NMI;

    // Hardware interface — w1c set strobes (testbench drives)
    logic        hw_IRQ_STS_IRQ0_PEND_set;
    logic        hw_IRQ_STS_IRQ1_PEND_set;
    logic        hw_IRQ_STS_IRQ2_PEND_set;

    // Hardware interface — rclr load (testbench drives)
    logic [3:0]  hw_FIFO_STS_EVT_COUNT;
    logic        hw_FIFO_STS_EVT_COUNT_en;

    // --------------------------------------------------------
    // DUT instantiation
    // --------------------------------------------------------

    irq_ctrl dut (
        .PCLK                    (PCLK),
        .PRESETn                 (PRESETn),
        .PADDR                   (PADDR),
        .PWRITE                  (PWRITE),
        .PSEL                    (PSEL),
        .PENABLE                 (PENABLE),
        .PWDATA                  (PWDATA),
        .PRDATA                  (PRDATA),
        .PREADY                  (PREADY),
        .hw_STATUS_BUSY          (hw_STATUS_BUSY),
        .hw_STATUS_IRQ           (hw_STATUS_IRQ),
        .hw_STATUS_ERR           (hw_STATUS_ERR),
        .hw_TRIG_SOFT_IRQ        (hw_TRIG_SOFT_IRQ),
        .hw_TRIG_SOFT_NMI        (hw_TRIG_SOFT_NMI),
        .hw_IRQ_STS_IRQ0_PEND_set(hw_IRQ_STS_IRQ0_PEND_set),
        .hw_IRQ_STS_IRQ1_PEND_set(hw_IRQ_STS_IRQ1_PEND_set),
        .hw_IRQ_STS_IRQ2_PEND_set(hw_IRQ_STS_IRQ2_PEND_set),
        .hw_FIFO_STS_EVT_COUNT   (hw_FIFO_STS_EVT_COUNT),
        .hw_FIFO_STS_EVT_COUNT_en(hw_FIFO_STS_EVT_COUNT_en)
    );

    // --------------------------------------------------------
    // Clock generator — 10 ns period (100 MHz)
    // --------------------------------------------------------

    initial PCLK = 1'b0;
    always  #5 PCLK = ~PCLK;

    // --------------------------------------------------------
    // APB tasks
    //
    // LEARNING NOTE — APB two-phase protocol:
    //
    //        negedge        negedge        posedge        negedge
    //          |    Setup     |   Access     |    Done      |
    //  PSEL    |__XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX________|
    //  PENABLE |______________|XXXXXXXXXXXXXXXXXXXXXX_______|
    //  PREADY  (tied high — always done in Access phase)
    //
    // We drive signals on the negedge (far from posedge) to give
    // the DUT maximum setup time. We sample PRDATA at the posedge
    // in the active region — before non-blocking assignment (NBA)
    // updates, so we read the pre-edge flop value (required for rclr).
    // --------------------------------------------------------

    task automatic apb_write(input logic [31:0] addr, input logic [31:0] data);
        // Setup phase: present address, data, direction
        @(negedge PCLK);
        PADDR   = addr;
        PWDATA  = data;
        PWRITE  = 1'b1;
        PSEL    = 1'b1;
        PENABLE = 1'b0;
        // Access phase: assert PENABLE; DUT flop captures at posedge
        @(negedge PCLK);
        PENABLE = 1'b1;
        @(posedge PCLK);   // DUT registers the write here (NBA fires after this)
        // Deassert: back to idle
        @(negedge PCLK);
        PSEL    = 1'b0;
        PENABLE = 1'b0;
        PWRITE  = 1'b0;
    endtask

    task automatic apb_read(input logic [31:0] addr, output logic [31:0] data);
        // Setup phase
        @(negedge PCLK);
        PADDR   = addr;
        PWRITE  = 1'b0;
        PSEL    = 1'b1;
        PENABLE = 1'b0;
        // Access phase
        @(negedge PCLK);
        PENABLE = 1'b1;
        // LEARNING NOTE — why we sample at posedge not after:
        //   For rclr fields the DUT schedules a clear (r <= 0) via a
        //   non-blocking assignment at this posedge. Non-blocking LHS
        //   updates (NBA region) come AFTER the active region where our
        //   `data = PRDATA` runs. So we observe the OLD value — the same
        //   value the real APB master would latch in hardware.
        @(posedge PCLK);
        data = PRDATA;
        // Deassert
        @(negedge PCLK);
        PSEL    = 1'b0;
        PENABLE = 1'b0;
    endtask

    // --------------------------------------------------------
    // Test logic
    // --------------------------------------------------------

    int          fail_count;
    logic [31:0] rdata;

    initial begin
        // --------------------------------------------------
        // Initialise all signals to safe defaults
        // --------------------------------------------------
        PRESETn                  = 1'b0;
        PSEL                     = 1'b0;
        PENABLE                  = 1'b0;
        PWRITE                   = 1'b0;
        PADDR                    = 32'h0;
        PWDATA                   = 32'h0;
        hw_STATUS_BUSY           = 1'b0;
        hw_STATUS_IRQ            = 1'b0;
        hw_STATUS_ERR            = 1'b0;
        hw_IRQ_STS_IRQ0_PEND_set = 1'b0;
        hw_IRQ_STS_IRQ1_PEND_set = 1'b0;
        hw_IRQ_STS_IRQ2_PEND_set = 1'b0;
        hw_FIFO_STS_EVT_COUNT    = 4'h0;
        hw_FIFO_STS_EVT_COUNT_en = 1'b0;
        fail_count               = 0;

        // Hold reset for 3 clock cycles, then release
        repeat(3) @(posedge PCLK);
        @(negedge PCLK);
        PRESETn = 1'b1;

        // ==================================================
        // TEST 1: rw — CTRL register (offset 0x00)
        //
        // CTRL fields:  ENABLE[0]  MODE[2:1]  PRIORITY[5:3]
        // Write value:  ENABLE=1, MODE=2 (binary 10), PRIORITY=5 (binary 101)
        // Packed word:  0b00_101_10_1 = 0x2D
        //
        // Real-world: this is how a driver configures a peripheral —
        // write a single word that sets multiple bit fields at once.
        // ==================================================
        $display("TEST 1: rw — CTRL write/readback");
        apb_write(32'h00, 32'h0000_002D);
        apb_read (32'h00, rdata);
        if (rdata[5:0] !== 6'h2D) begin
            $display("  FAIL: expected CTRL[5:0]=0x2D, got 0x%0x", rdata[5:0]);
            fail_count++;
        end else
            $display("  PASS: CTRL[5:0]=0x%0x (ENABLE=1 MODE=2 PRIORITY=5)", rdata[5:0]);

        // ==================================================
        // TEST 2: ro — STATUS register (offset 0x04)
        //
        // ro fields are wires from HW input ports — no flop.
        // Driving the input port is equivalent to hardware logic
        // asserting a status signal (e.g., a FIFO-full flag).
        //
        // Also verify that a write to a ro register is silently
        // ignored (a fundamental APB register-block contract).
        // ==================================================
        $display("TEST 2: ro — STATUS driven by HW ports, write ignored");
        hw_STATUS_BUSY = 1'b1;
        hw_STATUS_IRQ  = 1'b1;
        hw_STATUS_ERR  = 1'b0;
        apb_read(32'h04, rdata);
        if (rdata[2:0] !== 3'b011) begin
            $display("  FAIL: expected STATUS[2:0]=0x3, got 0x%0x", rdata[2:0]);
            fail_count++;
        end else
            $display("  PASS: STATUS[2:0]=0x%0x (BUSY=1 IRQ=1 ERR=0)", rdata[2:0]);

        // Write all-ones — should be silently ignored
        apb_write(32'h04, 32'hFFFF_FFFF);
        apb_read (32'h04, rdata);
        if (rdata[2:0] !== 3'b011) begin
            $display("  FAIL: ro write changed STATUS, got 0x%0x", rdata[2:0]);
            fail_count++;
        end else
            $display("  PASS: write to ro silently ignored, STATUS unchanged");

        // Restore HW inputs to 0
        hw_STATUS_BUSY = 1'b0;
        hw_STATUS_IRQ  = 1'b0;

        // ==================================================
        // TEST 3: wo — TRIG register (offset 0x0C)
        //
        // wo fields store the written value internally (so HW can
        // observe the pulse via the hw_ output port) but the read
        // mux hardwires PRDATA to 0 for this register.
        //
        // Real-world: a software interrupt trigger — the write fires
        // an event into the HW; reading back would be meaningless.
        // ==================================================
        $display("TEST 3: wo — TRIG write visible on HW port, readback=0");
        apb_write(32'h0C, 32'h3);   // SOFT_IRQ=1, SOFT_NMI=1
        // hw_TRIG_* are combinational assigns from the flops; valid after write
        if (hw_TRIG_SOFT_IRQ !== 1'b1 || hw_TRIG_SOFT_NMI !== 1'b1) begin
            $display("  FAIL: HW ports not driven (SOFT_IRQ=%0b SOFT_NMI=%0b)",
                     hw_TRIG_SOFT_IRQ, hw_TRIG_SOFT_NMI);
            fail_count++;
        end else
            $display("  PASS: HW ports SOFT_IRQ=%0b SOFT_NMI=%0b",
                     hw_TRIG_SOFT_IRQ, hw_TRIG_SOFT_NMI);

        apb_read(32'h0C, rdata);
        if (rdata !== 32'h0) begin
            $display("  FAIL: wo readback non-zero: 0x%08x", rdata);
            fail_count++;
        end else
            $display("  PASS: wo readback=0x0 (PRDATA hardwired to 0)");

        // ==================================================
        // TEST 4: w1c — IRQ_STS register (offset 0x08)
        //
        // Step 1: HW asserts hw_IRQ_STS_IRQ0_PEND_set for one cycle
        //         → DUT sets r_IRQ_STS_IRQ0_PEND = 1
        // Step 2: SW reads IRQ_STS → sees bit[0]=1 (interrupt pending)
        // Step 3: SW writes 1 to bit[0] → DUT clears the flop
        // Step 4: SW reads again → bit[0]=0 (acknowledged)
        //
        // Real-world: this is exactly how the ARM GIC and RISC-V PLIC
        // work — the interrupt controller sets a pending bit; the driver
        // ISR clears it by writing 1. Write-0 has no effect, so the
        // driver can safely write a single 1 without affecting other bits.
        // ==================================================
        $display("TEST 4: w1c — IRQ set by HW pulse, cleared by SW write-1");

        // Pulse the HW set strobe for one clock cycle
        @(negedge PCLK);
        hw_IRQ_STS_IRQ0_PEND_set = 1'b1;
        @(posedge PCLK);   // DUT flop set here
        @(negedge PCLK);
        hw_IRQ_STS_IRQ0_PEND_set = 1'b0;

        apb_read(32'h08, rdata);
        if (rdata[0] !== 1'b1) begin
            $display("  FAIL: IRQ0_PEND not set after HW pulse, bit[0]=%0b", rdata[0]);
            fail_count++;
        end else
            $display("  PASS: IRQ_STS=0x%0x — IRQ0_PEND set by HW", rdata[2:0]);

        // SW acknowledges: write 1 to bit[0]
        apb_write(32'h08, 32'h1);
        apb_read (32'h08, rdata);
        if (rdata[0] !== 1'b0) begin
            $display("  FAIL: IRQ0_PEND not cleared after SW write-1, bit[0]=%0b", rdata[0]);
            fail_count++;
        end else
            $display("  PASS: IRQ0_PEND cleared by SW write-1 (acknowledged)");

        // ==================================================
        // TEST 5: rclr — FIFO_STS register (offset 0x10)
        //
        // Step 1: HW loads EVT_COUNT=0xA via the _en strobe
        // Step 2: SW reads FIFO_STS → returns 0xA AND the DUT
        //         schedules a clear (via NBA) at that same posedge
        // Step 3: SW reads again → returns 0 (auto-cleared)
        //
        // LEARNING NOTE — why sampling works:
        //   The clear uses a non-blocking assignment (<=). Non-blocking
        //   LHS updates happen in the NBA region, AFTER the active region
        //   where we capture PRDATA. So the first read returns 0xA (the
        //   live flop value), and the second read returns 0.
        //
        // Real-world: event counters in UARTs and hardware monitors use
        // rclr — "how many events since last poll?" One read atomically
        // returns and resets the count.
        // ==================================================
        $display("TEST 5: rclr — HW loads value, auto-clears on SW read");

        // Load EVT_COUNT=0xA via HW enable strobe
        @(negedge PCLK);
        hw_FIFO_STS_EVT_COUNT    = 4'hA;
        hw_FIFO_STS_EVT_COUNT_en = 1'b1;
        @(posedge PCLK);   // DUT loads the value here
        @(negedge PCLK);
        hw_FIFO_STS_EVT_COUNT_en = 1'b0;

        // First read: should return 0xA; clear is scheduled at this posedge
        apb_read(32'h10, rdata);
        if (rdata[3:0] !== 4'hA) begin
            $display("  FAIL: first read expected 0xA, got 0x%0x", rdata[3:0]);
            fail_count++;
        end else
            $display("  PASS: FIFO_STS first read = 0x%0x", rdata[3:0]);

        // Second read: clear has taken effect (NBA fired after previous posedge)
        apb_read(32'h10, rdata);
        if (rdata[3:0] !== 4'h0) begin
            $display("  FAIL: rclr not cleared on second read, got 0x%0x", rdata[3:0]);
            fail_count++;
        end else
            $display("  PASS: FIFO_STS auto-cleared → second read = 0x%0x", rdata[3:0]);

        // ==================================================
        // Summary
        // ==================================================
        $display("-------------------------------");
        if (fail_count == 0) begin
            $display("ALL TESTS PASSED (5/5)");
            $finish;
        end else begin
            $display("%0d TEST(S) FAILED", fail_count);
            $fatal(1, "Simulation failed");
        end
    end

endmodule  // irq_ctrl_tb
