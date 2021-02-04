import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ..engine_advanced_settings import EngineAdvancedSettings
from ..engine import Engine
from ..utils import EXPAND_AND_FILL, PATTERN_PLACEHOLDER_TEXT

class CephS3BucketEngineAdvancedSettings(EngineAdvancedSettings):

    def __init__(self, engine: Engine):
        super().__init__(engine)

        self._row_counter = 0

        # Monitor existing files
        process_existing_files_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )
        self.attach(process_existing_files_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1

        process_existing_files_switch = engine.register_widget(Gtk.Switch(
            halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
            active=False), 'process_existing_files')
        process_existing_files_grid.attach(process_existing_files_switch, 0, 0, 1, 1)
        process_existing_files_grid.attach(Gtk.Label(
            label='Process existing files in bucket',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 1, 0, 1, 1)

        self._add_horizontal_separator()

        # Specify allowed file patterns
        allowed_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )

        self.attach(allowed_patterns_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1
        allowed_patterns_grid.attach(Gtk.Label(
                label='Allowed filename patterns',
                halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
                hexpand=False, vexpand=False,
            ),
            0, 0, 1, 1,
        )
        self._allowed_patterns_entry = engine.register_widget(Gtk.Entry(placeholder_text=PATTERN_PLACEHOLDER_TEXT,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
        ), 'allowed_patterns')
        allowed_patterns_grid.attach(self._allowed_patterns_entry, 1, 0, 1, 1)

        self._add_horizontal_separator()

        # Specify ignored file patterns
        ignore_patterns_grid = Gtk.Grid(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            column_spacing=5
        )

        self.attach(ignore_patterns_grid, 0, self._row_counter, 1, 1)
        self._row_counter += 1
        ignore_patterns_grid.attach(Gtk.Label(
            label='Ignored filename patterns',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,

        ),
            0, 0, 1, 1,
        )
        self._ignored_patterns_entry = engine.register_widget(Gtk.Entry(placeholder_text=PATTERN_PLACEHOLDER_TEXT,
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
        ), 'ignore_patterns')
        ignore_patterns_grid.attach(self._ignored_patterns_entry, 1, 0, 1, 1)

        self._add_horizontal_separator()

        # now the RabbitMQ config
        rabbitmq_radiobutton = engine.register_widget(Gtk.RadioButton(
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
            active=True, label='RabbitMQ push-endpoint'
        ), 'use_rabbitmq')

        rabbitmq_frame = Gtk.Frame(
            halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
            hexpand=True, vexpand=False,
            label_widget=rabbitmq_radiobutton
        )

        self.attach(rabbitmq_frame, 0, self._row_counter, 1, 1)
        self._row_counter += 1

        rabbitmq_grid = Gtk.Grid(**EXPAND_AND_FILL,
            row_spacing=5, column_spacing=5, border_width=5)
        rabbitmq_frame.add(rabbitmq_grid)

        # we need:
        # 1. rabbitmq hostname
        # 2. rabbitmq username
        # 3. rabbitmq password
        # 4. rabbitmq producer port
        # 5. rabbitmq producer use-ssl set false!!
        # 6. rabbitmq consumer port
        # 7. rabbitmq consumer use-ssl
        # 8. rabbitmq CA certificate file path
        # 9. rabbitmq exchange name
        # 10. rabbitmq vhost
        rabbitmq_grid.attach(Gtk.Label(
            label='Hostname',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 0, 1, 1)
        rabbitmq_hostname_entry = engine.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_hostname')
        rabbitmq_grid.attach(rabbitmq_hostname_entry, 1, 0, 2, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Username',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 1, 1, 1)
        rabbitmq_username_entry = engine.register_widget(
            Gtk.Entry(
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_username')
        rabbitmq_grid.attach(rabbitmq_username_entry, 1, 1, 2, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Password',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 2, 1, 1)
        rabbitmq_password_entry = engine.register_widget(
            Gtk.Entry(
                visibility=False,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_password', exportable=False)
        rabbitmq_grid.attach(rabbitmq_password_entry, 1, 2, 2, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Producer Port',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 3, 1, 1)
        rabbitmq_producer_port_spinbutton = engine.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=500,
                upper=50000,
                value=5672,
                page_size=0,
                step_increment=1),
            value=5672,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=1,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'rabbitmq_producer_port')
        rabbitmq_grid.attach(rabbitmq_producer_port_spinbutton, 1, 3, 1, 1)
        # Disable until there's a Ceph release that actually supports this...
        #rabbitmq_grid.attach(
        #    engine.register_widget(Gtk.CheckButton(
        #        label="Use SSL",
        #        halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
        #        hexpand=False, vexpand=False,
        #    ), 'rabbitmq_producer_use_ssl'), 2, 3, 1, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Consumer Port',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 4, 1, 1)
        rabbitmq_consumer_port_spinbutton = engine.register_widget(Gtk.SpinButton(
            adjustment=Gtk.Adjustment(
                lower=500,
                upper=50000,
                value=5672,
                page_size=0,
                step_increment=1),
            value=5672,
            update_policy=Gtk.SpinButtonUpdatePolicy.IF_VALID,
            numeric=True,
            climb_rate=1,
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False), 'rabbitmq_consumer_port')
        rabbitmq_grid.attach(rabbitmq_consumer_port_spinbutton, 1, 4, 1, 1)
        rabbitmq_grid.attach(
            engine.register_widget(Gtk.CheckButton(
                label="Use SSL",
                halign=Gtk.Align.END, valign=Gtk.Align.CENTER,
                hexpand=False, vexpand=False,
            ), 'rabbitmq_consumer_use_ssl'), 2, 4, 1, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='CA certificate',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 5, 1, 1)
        rabbitmq_ca_certificate = engine.register_widget(
            Gtk.FileChooserButton(
                title="Select the CA certificate used to sign the server SSL certificate",
                action=Gtk.FileChooserAction.OPEN,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_ca_certificate')
        rabbitmq_grid.attach(rabbitmq_ca_certificate, 1, 5, 2, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Exchange',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 6, 1, 1)
        rabbitmq_exchange_entry = engine.register_widget(
            Gtk.Entry(
                text='rfi-file-monitor-ceph',
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_exchange')
        rabbitmq_grid.attach(rabbitmq_exchange_entry, 1, 6, 2, 1)

        rabbitmq_grid.attach(Gtk.Label(
            label='Vhost',
            halign=Gtk.Align.START, valign=Gtk.Align.CENTER,
            hexpand=False, vexpand=False,
        ), 0, 7, 1, 1)
        rabbitmq_vhost_entry = engine.register_widget(
            Gtk.Entry(
                text='/',
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=False,
            ), 'rabbitmq_vhost')
        rabbitmq_grid.attach(rabbitmq_vhost_entry, 1, 7, 2, 1)

    def _add_horizontal_separator(self):
        self.attach(Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL,
                halign=Gtk.Align.FILL, valign=Gtk.Align.CENTER,
                hexpand=True, vexpand=True,
            ),
            0, self._row_counter, 1, 1
        )
        self._row_counter += 1