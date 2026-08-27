from app.discovery.extractors.contact import ContactExtractor


def test_contact_extractor_emails_and_phones():
    html_content = """
    <html>
    <body>
        <div class="header">
            <a href="tel:+919876543210">Call Us: +91 98765 43210</a>
            <a href="mailto:hello@drsmiledental.com">Email Us</a>
        </div>
        <div class="content">
            <p>For appointments, write to support@drsmiledental.com or call (080) 4123-4567.</p>
            <p>Our emergency contact is: emergency [at] drsmiledental [dot] com</p>
            <!-- Asset extension that should NOT be picked as email -->
            <img src="avatar@2x.png" alt="Doctor" />
        </div>
        <footer>
            <address>
                100 Ft Road, HAL 2nd Stage, Indiranagar, Bangalore 560038
            </address>
        </footer>
    </body>
    </html>
    """

    extractor = ContactExtractor()
    contacts = extractor.extract_contacts(html_content, "https://drsmiledental.com")

    emails = [e.value for e in contacts["emails"]]
    assert "hello@drsmiledental.com" in emails
    assert "support@drsmiledental.com" in emails
    assert "emergency@drsmiledental.com" in emails
    # Assert png false-positive email is excluded
    assert not any("avatar" in e for e in emails)

    phones = [p.value for p in contacts["phone_numbers"]]
    assert len(phones) >= 2

    assert contacts["address"] is not None
    assert "Indiranagar" in contacts["address"]
