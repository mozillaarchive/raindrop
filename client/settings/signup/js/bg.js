function changeBgcolor() {
document.bgColor = document.colorChange.text.value
document.colorChange.colorValue.value = ""
}
function randomBg() {
var hex1=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var hex2=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var hex3=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var hex4=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var hex5=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var hex6=new Array("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F")
var bg="#"+hex1[Math.floor(Math.random()*hex1.length)]+hex2[Math.floor(Math.random()*hex2.length)]+hex3[Math.floor(Math.random()*hex3.length)]+hex4[Math.floor(Math.random()*hex4.length)]+hex5[Math.floor(Math.random()*hex5.length)]+hex6[Math.floor(Math.random()*hex6.length)]
document.bgColor = bg
document.colorChange.colorValue.value = bg
document.colorChange.text.value = ""
}
function timedChange() {
millisecs = document.colorChange.millisec
hexchanger = setInterval("randomBg()", millisecs.value)
}
function timedChangestop() {
clearInterval(hexchanger)
}