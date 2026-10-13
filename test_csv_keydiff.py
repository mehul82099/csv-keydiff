"""Offline regression tests. Run: python3 -m unittest -v"""
import contextlib
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from csv_keydiff import InputError, compare, load_table, main


def table(text, keys=None, **kw):
    return load_table(io.StringIO(text, newline=""), keys or ["id"], **kw)


class ComparisonTests(unittest.TestCase):
    def diff(self, a, b, keys=None, ignore=None):
        keys = keys or ["id"]
        return compare(table(a, keys), table(b, keys), keys, ignore)

    def test_reordered_rows_and_columns(self):
        r = self.diff('id,name\n1,A\n2,B\n', 'name,id\nB,2\nA,1\n')
        self.assertFalse(r['summary']['has_differences'])
        self.assertEqual(r['summary']['unchanged'], 2)

    def test_added_removed_changed(self):
        r = self.diff('id,n\n1,A\n2,B\n', 'id,n\n1,C\n3,D\n')
        self.assertEqual([r['summary'][k] for k in ('added','removed','changed')], [1,1,1])
        self.assertEqual(r['changed'][0]['cells']['n'], {'before':'A','after':'C'})

    def test_composite_keys(self):
        r = self.diff('order,line,n\n1,1,A\n1,2,B\n',
                      'line,n,order\n2,C,1\n1,A,1\n', ['order','line'])
        self.assertEqual(r['changed'][0]['key'], {'order':'1','line':'2'})

    def test_tuple_keys_do_not_collide(self):
        t = table('a,b,n\n"a,b",c,1\na,"b,c",2\n', ['a','b'])
        self.assertEqual(len(t.rows), 2)

    def test_leading_zeros_preserved(self):
        r = self.diff('id,n\n001,A\n', 'id,n\n1,A\n')
        self.assertEqual(r['summary']['added'], 1)
        self.assertEqual(r['summary']['removed'], 1)

    def test_numeric_spelling_preserved(self):
        r = self.diff('id,n\n1,1.00\n', 'id,n\n1,1.0\n')
        self.assertEqual(r['summary']['changed'], 1)

    def test_whitespace_is_significant(self):
        r = self.diff('id,n\n1,A\n', 'id,n\n1,A \n')
        self.assertEqual(r['summary']['changed'], 1)

    def test_schema_changes_and_header_only(self):
        r = self.diff('id,old\n', 'id,new\n')
        self.assertEqual(r['columns'], {'added':['new'],'removed':['old']})
        self.assertTrue(r['summary']['has_differences'])

    def test_schema_only_does_not_mark_common_cells_changed(self):
        r = self.diff('id,old\n1,x\n', 'id,new\n1,y\n')
        self.assertEqual(r['summary']['changed'], 0)
        self.assertEqual(r['summary']['unchanged'], 1)
        self.assertTrue(r['summary']['has_differences'])

    def test_ignore(self):
        r = self.diff('id,updated,n\n1,x,A\n', 'id,updated,n\n1,y,A\n', ignore=['updated'])
        self.assertFalse(r['summary']['has_differences'])

    def test_ignore_missing(self):
        with self.assertRaises(InputError):
            self.diff('id,n\n', 'id,n\n', ignore=['typo'])

    def test_ignore_key(self):
        with self.assertRaises(InputError):
            self.diff('id,n\n', 'id,n\n', ignore=['id'])

    def test_unicode_and_multiline(self):
        t = table('id,n\n1,"नमस्ते, hello\nsecond ""line"""\n')
        self.assertEqual(t.rows[('1',)]['n'], 'नमस्ते, hello\nsecond "line"')

    def test_tab(self):
        t = table('id\tn\n1\tA\n', delimiter='\t')
        self.assertEqual(t.rows[('1',)]['n'], 'A')

    def test_semicolon(self):
        t = table('id;n\n1;A\n', delimiter=';')
        self.assertEqual(t.rows[('1',)]['n'], 'A')

    def test_formula_remains_plain_text(self):
        t = table('id,n\n1,=1+1\n')
        self.assertEqual(t.rows[('1',)]['n'], '=1+1')

    def test_duplicate_key(self):
        with self.assertRaisesRegex(InputError, 'records 2 and 3'):
            table('id,n\nsecret,A\nsecret,B\n')

    def test_duplicate_error_does_not_echo_key(self):
        with self.assertRaises(InputError) as e:
            table('id,n\nprivate-key,A\nprivate-key,B\n')
        self.assertNotIn('private-key', str(e.exception))

    def test_duplicate_header(self):
        with self.assertRaises(InputError): table('id,id\n1,2\n')

    def test_blank_header(self):
        with self.assertRaises(InputError): table('id, \n1,A\n')

    def test_missing_header(self):
        with self.assertRaises(InputError): table('')

    def test_missing_key(self):
        with self.assertRaises(InputError): table('name\nA\n')

    def test_blank_key(self):
        for value in ('', ' ', '\t'):
            with self.subTest(value=value), self.assertRaises(InputError):
                table('id,n\n' + value + ',A\n')

    def test_ragged_row(self):
        for text in ('id,n\n1\n', 'id,n\n1,A,B\n', 'id,n\n\n'):
            with self.subTest(text=text), self.assertRaises(InputError): table(text)

    def test_unclosed_quote(self):
        with self.assertRaises(InputError): table('id,n\n1,"unclosed')

    def test_row_limit(self):
        with self.assertRaises(InputError): table('id\n1\n2\n', max_rows=1)

    def test_bad_delimiter(self):
        for delim in ('', 'ab', '\n', '"'):
            with self.subTest(delim=delim), self.assertRaises(InputError):
                table('id\n1\n', delimiter=delim)

    def test_duplicate_requested_keys(self):
        with self.assertRaises(InputError): table('id\n1\n', ['id','id'])

    def test_deterministic_permutations(self):
        rng = random.Random(42)
        original = 'id,n\n' + ''.join(f'{i},v{i}\n' for i in range(100))
        for _ in range(20):
            order = list(range(100)); rng.shuffle(order)
            shuffled = 'n,id\n' + ''.join(f'v{i},{i}\n' for i in order)
            self.assertFalse(self.diff(original, shuffled)['summary']['has_differences'])


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a, self.b = [Path(self.tmp.name) / n for n in ('a.csv','b.csv')]
        self.a.write_text('id,n\n001,A\n', encoding='utf-8-sig')
        self.b.write_text('id,n\n001,A\n', encoding='utf-8')

    def run_cli(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main([str(self.a), str(self.b), '--key', 'id', *extra])
        return code, out.getvalue(), err.getvalue()

    def test_bom_and_equal_exit(self):
        code, out, err = self.run_cli()
        self.assertEqual(code, 0); self.assertFalse(err)
        self.assertFalse(json.loads(out)['summary']['has_differences'])

    def test_changed_exit(self):
        self.b.write_text('id,n\n001,B\n')
        code, out, err = self.run_cli()
        self.assertEqual(code, 1); self.assertEqual(json.loads(out)['summary']['changed'], 1)

    def test_invalid_exit_no_partial_json(self):
        self.b.write_text('id,n\n001,A\n001,B\n')
        code, out, err = self.run_cli()
        self.assertEqual(code, 2); self.assertEqual(out, ''); self.assertIn('duplicate', err)

    def test_missing_file(self):
        self.b.unlink()
        self.assertEqual(self.run_cli()[0], 2)

    def test_invalid_encoding(self):
        self.assertEqual(self.run_cli('--encoding', 'not-a-codec')[0], 2)

    def test_output_does_not_overwrite_input(self):
        old = self.a.read_bytes()
        self.assertEqual(self.run_cli('--output', str(self.a))[0], 2)
        self.assertEqual(self.a.read_bytes(), old)

    def test_new_output(self):
        dest = Path(self.tmp.name) / 'report.json'
        code, out, err = self.run_cli('--output', str(dest))
        self.assertEqual(code, 0); self.assertEqual(out, '')
        self.assertEqual(json.loads(dest.read_text())['format_version'], 1)

    def test_output_does_not_overwrite_existing_report(self):
        dest = Path(self.tmp.name) / 'report.json'; dest.write_text('keep')
        self.assertEqual(self.run_cli('--output', str(dest))[0], 2)
        self.assertEqual(dest.read_text(), 'keep')

    def test_invalid_utf8(self):
        self.b.write_bytes(b'id,n\n1,\xff\n')
        self.assertEqual(self.run_cli()[0], 2)

    def test_tab_cli(self):
        for f in (self.a, self.b): f.write_text('id\tn\n1\tA\n')
        self.assertEqual(self.run_cli('--delimiter', r'\t')[0], 0)


if __name__ == '__main__':
    unittest.main()
