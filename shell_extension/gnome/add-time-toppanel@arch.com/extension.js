const St = imports.gi.St;
const Main = imports.ui.main;
const GnomeDesktop = imports.gi.GnomeDesktop;
const Lang = imports.lang;
const Shell = imports.gi.Shell;
const Clutter = imports.gi.Clutter;
var Gio = imports.gi.Gio;

let text, label;
let clock, clock_signal_id;
let y = new Date();

let time_text = "Time left: Not set";

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
    powerIndicator.remove_child(label);
    clock.disconnect(clock_signal_id);
}

//function update_time() {
//    var now = new Date();
//    label.set_text((now.getTime()).toString());
//}

function update_time() {

    //let script = ['/bin/bash', '/usr/local/bin/timeleft.sh'];
    let script = ['/usr/local/bin/timeleft'];

    // Create subprocess and capture STDOUT
    let proc = new Gio.Subprocess({argv: script, flags: Gio.SubprocessFlags.STDOUT_PIPE});
    proc.init(null);
    // Asynchronously call the output handler when script output is ready
    proc.communicate_utf8_async(null, null, Lang.bind(this, this.handleOutput));
    label.set_text(time_text);
}

function handleOutput(proc, result) {
    let [ok, output, ] = proc.communicate_utf8_finish(result);
    if (ok) {
	global.logError(output);
	time_text = output;
    } else {
        global.logError('script invocation failed');
    }
}
