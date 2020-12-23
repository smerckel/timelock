const St = imports.gi.St;
const Main = imports.ui.main;
const GnomeDesktop = imports.gi.GnomeDesktop;
const Lang = imports.lang;
const Shell = imports.gi.Shell;
const Clutter = imports.gi.Clutter;

let text, label;
let clock, clock_signal_id;
let y = new Date();


function init() {
    clock = new GnomeDesktop.WallClock();
    label = new St.Label({ text: y.getTime().toString()    , y_align: Clutter.ActorAlign.CENTER, x_align: Clutter.ActorAlign.CENTER, style_class: "year-label" });
    aggregateMenu = Main.panel.statusArea["aggregateMenu"];
    powerIndicator = aggregateMenu._power.indicators;
}

function enable() {
    update_time();
    clock_signal_id = clock.connect('notify::clock', Lang.bind(this, this.update_time));
    powerIndicator.add_child(label);
}

function disable() {
    clock.disconnect(clock_signal_id);
}

function update_time() {
    var now = new Date();
    label.set_text((now.getTime()).toString());
}