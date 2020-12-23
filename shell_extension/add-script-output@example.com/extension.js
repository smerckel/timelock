// Example #1

const {St, Clutter} = imports.gi;
const Main = imports.ui.main;
const Mainloop = imports.mainloop;
const Lang = imports.lang;
const Gio = imports.gi.Gio;


let panelButton, panelButtonText;
let timeout_func;

function init () {
    // Create a Button with "Hello World" text
    panelButton = new St.Bin({
        style_class : "panel-button",
    });
    panelButtonText = new St.Label({
        text : "Time left : --- minutes",
        y_align: Clutter.ActorAlign.CENTER,
	style_class: "panel_button_text"
    });
    panelButton.set_child(panelButtonText);
}

function enable () {
    // Add the button to the panel
    Main.panel._rightBox.insert_child_at_index(panelButton, 0);
    update_time();
}

function disable () {
    // Remove the added button from panel
    Main.panel._rightBox.remove_child(panelButton);
    Mainloop.source_remove(timeout_func); //stops timer function
}


function run_script() {

    let script = ['/usr/local/bin/timeleft'];
    // Create subprocess and capture STDOUT
    let proc = new Gio.Subprocess({argv: script, flags: Gio.SubprocessFlags.STDOUT_PIPE});
    proc.init(null);
    // Asynchronously call the output handler when script output is ready
    proc.communicate_utf8_async(null, null, Lang.bind(this, this.handle_output));
}

function handle_output(proc, result) {
    let [ok, output, ] = proc.communicate_utf8_finish(result);
    if (ok) {
	panelButtonText.set_text(output);
    } else {
        global.logError('script invocation failed');
    }
}



function update_time() {
    run_script();
    timeout_func=Mainloop.timeout_add_seconds(60, Lang.bind(this, this.update_time));
}
