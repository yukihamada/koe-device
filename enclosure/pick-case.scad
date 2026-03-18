// Koe Pick — Guitar pick shaped case for ESP32-S3-MINI-1 + INMP441 + MAX98357A
// OpenSCAD file — export as STL for 3D printing
// Units: mm

// Parameters
wall = 1.5;          // Wall thickness
pcb_w = 25;          // PCB width
pcb_h = 30;          // PCB height
pcb_t = 1.0;         // PCB thickness
total_t = 8;         // Total device thickness
corner_r = 3;        // Corner radius
split = total_t / 2; // Split line for two-piece case

// Pick shape (rounded triangle)
module pick_shape(h) {
    hull() {
        // Top vertex (rounded)
        translate([pcb_w/2, pcb_h - 5, 0])
            cylinder(r=8, h=h, $fn=60);
        // Bottom left
        translate([5, 5, 0])
            cylinder(r=5, h=h, $fn=60);
        // Bottom right
        translate([pcb_w - 5, 5, 0])
            cylinder(r=5, h=h, $fn=60);
    }
}

// Bottom half
module bottom() {
    difference() {
        pick_shape(split);

        // Hollow inside
        translate([0, 0, wall])
            offset(r=-wall)
                pick_shape(split);

        // USB-C port (bottom edge)
        translate([pcb_w/2 - 4.5, -1, wall + 0.5])
            cube([9, wall + 2, 3.5]);

        // LED window (center)
        translate([pcb_w/2, pcb_h/2, -0.1])
            cylinder(r=1.5, h=wall + 0.2, $fn=30);
    }

    // PCB support standoffs (4x)
    for (pos = [[7, 8], [pcb_w-7, 8], [7, pcb_h-10], [pcb_w-7, pcb_h-10]]) {
        translate([pos[0], pos[1], wall])
            cylinder(r=1.2, h=1.5, $fn=20);
    }
}

// Top half
module top() {
    difference() {
        pick_shape(split);

        // Hollow inside
        translate([0, 0, -0.1])
            offset(r=-wall)
                pick_shape(split + 0.1);

        // Microphone hole (top area)
        translate([pcb_w/2, pcb_h - 8, split - wall - 0.1])
            cylinder(r=1.5, h=wall + 0.2, $fn=30);

        // Speaker grille (array of holes)
        for (x = [-3:1.5:3]) {
            for (y = [-3:1.5:3]) {
                if (sqrt(x*x + y*y) < 4) {
                    translate([pcb_w/2 + x, 12 + y, split - wall - 0.1])
                        cylinder(r=0.5, h=wall + 0.2, $fn=15);
                }
            }
        }

        // Button access hole
        translate([-0.1, pcb_h/2, split/2])
            rotate([0, 90, 0])
                cylinder(r=1, h=wall + 0.2, $fn=20);
    }
}

// Pendant loop
module loop() {
    translate([pcb_w/2, pcb_h + 2, split/2])
        difference() {
            cylinder(r=3, h=3, center=true, $fn=30);
            cylinder(r=1.5, h=4, center=true, $fn=30);
        }
}

// Render
color("DimGray") bottom();
color("DimGray") translate([0, 0, split + 0.5]) top();
color("Silver") loop();
