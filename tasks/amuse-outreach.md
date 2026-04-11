# Amuse Inc. — Manager Pre-Approval Draft
*Koe Sessions Recording Consent — Pre-Hawaii outreach*
*Send via: Hamada Yuuki → Manager, or direct email if contact known*

---

## Timeline
- **Send by:** 2026-06-01 (4 weeks before July 1 arrival)
- **Response needed by:** 2026-06-15
- **Fallback:** If no response, disable Sessions microphone arrays before July 1 arrival

---

## Draft Message (Japanese — Manager)

---

件名：ハワイ滞在中のKoe音声デバイスについて（任意・プライバシー重視）

お世話になっております。
濱田（ハワイの自宅で皆さんをお迎えする予定）の知人の濱田祐樹と申します。

7月の滞在に合わせて、自分が開発している音楽スピーカーシステム「Koe」をお部屋に設置させていただく予定です。

そのうちAmpというユニットには、楽器演奏の瞬間を自動的にキャプチャする機能（Koe Sessions）が搭載されています。「録音ボタンを押す前に始まっていた演奏」を逃さないための機能で、ギターや歌声を検知したときだけ動作します（会話は録音しません）。

録音はすべてデバイス内にローカル保存され、クラウドにはアップロードされません。30日後に自動削除されますが、アーティスト側で保存を選択することもできます。Koeは録音の権利を一切主張しません。

もし、この機能を有効にすることに問題がある場合は、到着前にオフにいたします。有効にする場合は、下記の同意書（PDF）に署名いただければ幸いです。もちろん強制ではなく、Koe自体はSessions機能なしでも十分に楽しんでいただけます。

同意書：koe.live/sessions/consent-form.pdf（英日両語）

何かご不明な点があれば、お気軽にご連絡ください。
すてきな滞在になるよう準備を進めています。

濱田祐樹
yukihamada@enablerdao.com

---

## Draft Message (English — if preferred)

---

Subject: Koe audio devices at the Hawaii house — optional recording consent

Hi [Manager Name],

I'm Yuki Hamada, a friend of Oki's (hosting everyone in Hawaii in July).

I'm placing a set of my audio speaker system, Koe, throughout the house for the stay. Most units are simple wireless speakers. However, two of the Amp units have a passive instrument capture feature called Koe Sessions — it listens for guitar, vocals, or bass, and begins recording automatically only when an instrument is playing (not conversation).

All recordings are stored locally on the device only. Nothing goes to the cloud. Recordings auto-delete after 30 days unless the artist explicitly saves them. Koe claims zero ownership of any recordings.

If you'd prefer this feature disabled before arrival, I'll turn it off, no questions. If everyone's comfortable, the consent form is at koe.live/sessions/consent-form.pdf — it's straightforward and short.

Let me know either way by June 15.

Best,
Yuki Hamada
yukihamada@enablerdao.com

---

## Decision Tree

```
Manager responds YES → sessions enabled, consent form signed, archive URL ready
Manager responds NO  → disable Amp mic arrays before 2026-06-30
Manager ignores      → default OFF (disable before arrival)
No manager contact available → ask Oki directly, default OFF
```

## Sessions URL to prepare
`koe.live/sessions/hawaii-2026-07` — private page (needs auth layer before July 1)
- Password: generate at consent time
- Contents: track listing, 30-day countdown, download links
- Auto-delete: 2026-08-01

---

## Next Steps

- [ ] Get Amuse Inc. manager name + contact from 濱田優貴
- [ ] Send outreach by 2026-06-01
- [ ] Build `koe.live/sessions/hawaii-2026-07` private page
- [ ] Generate consent-form.pdf from `tasks/sessions-consent-form.md`
- [ ] Set sessions disable date: 2026-06-30 if no confirmation
