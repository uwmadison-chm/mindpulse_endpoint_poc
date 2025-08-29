document.addEventListener("DOMContentLoaded", function() {
  
  const setup_qr = function() {
    console.log("I am in setup_qr")
    const key = document.getElementById("key").innerHTML
    
    const qr_generator = new QRCode('qrcode', {
      'text': key,
      'width': 512,
      'height': 512,
      'correctLevel': QRCode.CorrectLevel.Q,
    })
  }
  
  const setup_copier = function() {
    const copier = document.getElementById("copier")
    copier.addEventListener("click", function () {
      const key = document.getElementById("key").innerHTML
      const short_sha = document.getElementById("short_sha").innerHTML
      const cb_str = `${key}\t${short_sha}`
      console.log(cb_str)
      navigator.clipboard.writeText(cb_str)
    })
  }

  if (document.getElementById("qrcode")) { setup_qr() }
  if (document.getElementById("copier")) { setup_copier() }
})