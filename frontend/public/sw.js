self.addEventListener('push', e => {
  const data = e.data?.json() || {}
  self.registration.showNotification(data.title || 'Eidetic', {
    body: data.body || '',
    icon: '/cpu-schematic.svg',
    data: { url: data.url || '/' }
  })
})

self.addEventListener('notificationclick', e => {
  e.notification.close()
  e.waitUntil(
    clients.matchAll({ type: 'window' }).then(clist => {
      const c = clist.find(c => c.url === '/' && 'focus' in c)
      return c ? c.focus() : clients.openWindow(e.notification.data.url)
    })
  )
})
