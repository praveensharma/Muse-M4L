"""Graph-level regression tests; these do not run Max or emulate Live scheduling."""
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_device as G

BANG = 'bang'

class Graph:
    """Execute the small synchronous Max subset used by the repaired routes.

    midiformat is an event boundary here, not a substitute for a MIDI capture.
    Load-time scheduling, ctlin input delivery, UI drawing and Live persistence
    require testing inside Live.
    """
    def __init__(self):
        self.patch = G.build().to_maxpat()
        self.boxes = {b['box']['id']: b['box'] for b in self.patch['patcher']['boxes']}
        self.names = {b['varname']: i for i,b in self.boxes.items() if 'varname' in b}
        self.wires = {}
        self.state = {}
        self.output = []
        for b in self.boxes.values():
            t = b.get('text', '')
            if t == 'i 1': self.state[b['id']] = 1
            if t.startswith('gate '): self.state[b['id']] = 0
        for item in self.patch['patcher']['lines']:
            l = item['patchline']
            self.wires.setdefault(tuple(l['source']), []).append(tuple(l['destination']))

    def emit(self, oid, value, outlet=0):
        for dst, inlet in self.wires.get((oid, outlet), []):
            self.receive(dst, value, inlet)

    def control(self, name, value):
        self.receive(self.names[name], value)

    def receive(self, oid, value, inlet=0):
        b = self.boxes[oid]; t = b.get('text', ''); c = b['maxclass']
        if c.startswith('live.') or c == 'textbutton':
            if isinstance(value, list) and value[0] == 'set':
                self.state[oid] = value[1]; return
            if value == BANG:
                if c in ('live.text','textbutton') and b.get('mode') == 0: pass
                elif c == 'textbutton': value = 1 - self.state.get(oid, 0)
                else: value = self.state.get(oid, 0)
            self.state[oid] = value
            self.emit(oid, value); return
        if c == 'message':
            if t.startswith('script '): return
            if t.startswith('set '): value = ['set', int(t.split()[1])]
            else:
                atoms = list(map(int, t.split()))
                value = atoms[0] if len(atoms) == 1 else atoms
            self.emit(oid, value); return
        if c == 'loadbang': self.emit(oid, BANG); return
        if t.startswith('gate '):
            if inlet == 0: self.state[oid] = value
            elif self.state[oid]: self.emit(oid, value)
            return
        if t == 'i 1':
            if inlet == 1: self.state[oid] = value
            else:
                if value != BANG: self.state[oid] = value
                self.emit(oid, self.state[oid])
            return
        if t.startswith('t '):
            types = t.split()[1:]
            for n in reversed(range(len(types))):
                self.emit(oid, BANG if types[n] == 'b' else value, n)
            return
        if t.startswith('sel '):
            choices = list(map(int, t.split()[1:]))
            self.emit(oid, BANG if value in choices else value,
                      choices.index(value) if value in choices else len(choices))
            return
        if t.startswith('prepend '):
            atom = t.split()[1]
            try: atom = int(atom)
            except ValueError: pass
            self.emit(oid, [atom] + (value if isinstance(value,list) else [value])); return
        if t.startswith('expr '):
            expr = t[5:].replace('$i1', str(value))
            assert re.fullmatch(r'[0-9 ()+*/><=-]+', expr)
            self.emit(oid, int(eval(expr, {'__builtins__': {}}))); return
        if t.startswith(('* ', '- ', '>= ')):
            op, n = t.split(); n=int(n)
            result = value*n if op=='*' else value-n if op=='-' else int(value>=n)
            self.emit(oid, result); return
        if t.startswith('midiformat '):
            if inlet == 2: result = ('cc', *value)
            elif inlet == 3: result = ('pc', value)
            elif inlet == 5: result = ('bend', value)
            else: raise AssertionError(('unhandled MIDI inlet', inlet))
            self.emit(oid, result); return
        if t == 'midiout': self.output.append(value); return
        if t in ('thispatcher', 'delay 300', 'xbendin'): return
        raise AssertionError(('unhandled object', t, c, value, inlet))

    def input_bytes(self, values):
        source = next(i for i,b in self.boxes.items() if b.get('text')=='midiin')
        for value in values: self.emit(source, value)

    def feedback(self, cc, value):
        source = next(i for i,b in self.boxes.items() if b.get('text')==f'ctlin {cc}')
        self.emit(source, value)

class TonightTests(unittest.TestCase):
    def setUp(self): self.g = Graph()

    def test_ports_and_names(self):
        g=self.g
        for (src,outlet), destinations in g.wires.items():
            self.assertLess(outlet,g.boxes[src]['numoutlets'])
            for dst,inlet in destinations: self.assertLess(inlet,g.boxes[dst]['numinlets'])
        names=[b['varname'] for b in g.boxes.values() if 'varname' in b]
        self.assertEqual(len(names),len(set(names)))
        for b in g.boxes.values():
            if b.get('text','').startswith('midiformat '): self.assertEqual(b['numinlets'],7)
            if b.get('text','').startswith('ctlin '): self.assertEqual(b['numoutlets'],2)

    def test_startup_and_restore_are_silent(self):
        g=self.g
        for i,b in g.boxes.items():
            if b['maxclass']=='loadbang': g.receive(i,BANG)
        # Deliberately emit all restored parameter values, including selectors.
        for cc,name,kind,enum,short in G.iter_controls():
            g.control(G.slug(name), 1 if enum else 100)
        g.control('PCBank',16);g.control('PCPatch',16)
        g.input_bytes([144,60,100,176,67,80,128,60,0])
        self.assertEqual(g.output,[])
        g.control('OutputEnable',1)
        self.assertEqual(g.output,[])  # arming never pushes an INIT patch
        g.control('Filter_1_Cutoff',100)
        self.assertEqual(g.output,[('cc',67,100)])

    def test_send_is_only_preset_trigger_and_order_is_correct(self):
        g=self.g;g.control('OutputEnable',1)
        for bank,patch in [(1,1),(2,1),(16,16)]:
            g.control('PCBank',bank);g.control('PCPatch',patch)
            self.assertEqual(g.output,[])
            g.control('PCSend',BANG)
            self.assertEqual(g.output,[('cc',0,0),('cc',32,bank),('pc',patch-1)])
            g.output.clear()

    def test_send_reads_silently_restored_selectors(self):
        g=self.g;g.control('OutputEnable',1)
        g.control('PCBank',['set',16]);g.control('PCPatch',['set',16])
        self.assertEqual(g.output,[])
        g.control('PCSend',BANG)
        self.assertEqual(g.output,[('cc',0,0),('cc',32,16),('pc',15)])

    def test_send_while_disarmed_is_silent(self):
        self.g.control('PCSend',BANG)
        self.assertEqual(self.g.output,[])

    def test_hardware_feedback_does_not_echo(self):
        g=self.g;g.control('OutputEnable',1)
        g.input_bytes([176,67,100]);g.feedback(67,100)
        self.assertEqual(g.output,[])
        self.assertEqual(g.state[g.names['Filter_1_Cutoff']],100)
        g.feedback(54,127);g.feedback(44,64)
        self.assertEqual(g.output,[])
        self.assertEqual(g.state[g.names['OSC_2_1_Sync']],1)
        self.assertEqual(g.state[g.names['OSC_1_Octave']],2)

    def test_performance_thru_preserves_notes_and_controls(self):
        g=self.g;g.control('OutputEnable',1);g.control('MidiThru',1)
        stream=[144,60,100,176,64,127,208,96,224,0,64,128,60,0,176,64,0]
        g.input_bytes(stream)
        self.assertEqual(g.output,stream)

    def test_panic_and_disarming_release_notes(self):
        g=self.g
        expected=[('cc',64,0),('cc',71,0),('cc',123,0),('cc',120,0)]
        for name in ['HeaderPanic','MiscPanic']:
            g.control(name,BANG);self.assertEqual(g.output,expected);g.output.clear()
        g.control('OutputEnable',1);g.control('MidiThru',1)
        g.control('OutputEnable',0)
        self.assertEqual(g.output,expected);g.output.clear()
        g.input_bytes([144,60,100]);g.control('Filter_1_Cutoff',100)
        self.assertEqual(g.output,[])

    def test_header_not_stored_or_hidden_with_tabs(self):
        g=self.g
        for name in ['OutputEnable','MidiThru','HeaderPanic']:
            b=g.boxes[g.names[name]]
            self.assertEqual(b['parameter_enable'],0)
            self.assertNotIn('saved_attribute_attributes',b)
            self.assertFalse(any('script hide '+name in x.get('text','') for x in g.boxes.values()))
        for b in g.boxes.values():
            if b.get('presentation'):
                x,y,w,h=b['presentation_rect']
                self.assertLessEqual(y+h,169);self.assertLessEqual(x+w,G.DEVICE_WIDTH)

    def test_every_control_routes_correct_cc_and_enum_band(self):
        import csv
        with (Path(G.__file__).parent/'Muse_MIDI_CCs.csv').open(newline='') as source:
            rows={int(r['cc_msb']):r for r in csv.DictReader(source)}
        g=self.g;g.control('OutputEnable',1)
        for cc,name,kind,enum,short in G.iter_controls():
            if cc is None: continue
            values=range(len(enum)) if kind==G.M else [0,1] if kind==G.T else [0,127]
            for value in values:
                g.control(G.slug(name),value)
                self.assertEqual(len(g.output),1,(name,value,g.output))
                typ,outcc,data=g.output.pop()
                self.assertEqual((typ,outcc),('cc',cc))
                if kind==G.M:
                    bands=re.findall(r'(\d+)-(\d+):',rows[cc]['usage'])
                    self.assertEqual(len(bands),len(enum))
                    lo,hi=map(int,bands[value]);self.assertTrue(lo<=data<=hi,(name,value,data))
                else: self.assertEqual(data,value*127 if kind==G.T else value)

    def test_session_buttons_are_native_clickable_toggles(self):
        g=self.g
        for name in ('OutputEnable','MidiThru'):
            b=g.boxes[g.names[name]]
            self.assertEqual(b['maxclass'],'textbutton')
            self.assertEqual(b['mode'],1)
            self.assertEqual(b['active'],1)
            self.assertEqual(b['ignoreclick'],0)
            self.assertEqual(b['numoutlets'],3)
            g.control(name,BANG)
            self.assertEqual(g.state[g.names[name]],1)
            g.control(name,BANG)
            self.assertEqual(g.state[g.names[name]],0)

    def test_amxd_roundtrip(self):
        p=self.g.patch;blob=G.build_amxd(p,'mmmm','MuseEditor Tonight.amxd')
        embedded=json.loads(blob[blob.index(b'{'):blob.rindex(b'}')+1])
        self.assertEqual(p,embedded)
        self.assertEqual(blob[:12],b'ampf\x04\x00\x00\x00mmmm')

if __name__ == '__main__': unittest.main(verbosity=2)
