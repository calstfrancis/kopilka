Name:           kopilka
Version:        %{version}
Release:        1%{?dist}
Summary:        Couples budget planner built with GTK 4 and libadwaita
License:        GPL-3.0-only
URL:            https://github.com/calstfrancis/kopilka
Source0:        kopilka-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  python3-pip

Requires:       python3
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires:       typelib(Gtk) = 4.0
Requires:       typelib(Adw) = 1

%description
Kopilka is a couples budget planner for two-person households.
It tracks income, fixed expenses, debt, and discretionary spending
across shared categories. The budget lives in a single JSON file;
sync happens via WebDAV. Built with GTK 4 and libadwaita.

%prep
%autosetup -n kopilka-%{version}

%build
%py3_build

%install
%py3_install

# Install desktop entry and icon
install -Dm644 io.github.calstfrancis.kopilka.desktop \
    %{buildroot}%{_datadir}/applications/io.github.calstfrancis.kopilka.desktop

%files
%license pyproject.toml
%doc README.md CHANGELOG.md
%{python3_sitelib}/kopilka/
%{python3_sitelib}/kopilka-%{version}.dist-info/
%{_bindir}/kopilka
%{_datadir}/applications/io.github.calstfrancis.kopilka.desktop

%changelog
* Fri Jun 06 2026 Cal St Francis <calstfrancis@gmail.com> - 0.5.0-1
- v0.5.0: delete confirmation dialogs, Today buttons, friendly date headers, bug fixes

* Mon Jun 02 2026 Cal St Francis <calstfrancis@gmail.com> - 0.3.0-1
- Initial RPM package
