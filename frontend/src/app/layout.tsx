import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'The Doppelklick Times - AI Content Intelligence',
  description: '121 TikTok-Transkripte. Ein AI-Gehirn. Frag mich alles uber Content Marketing.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  )
}
