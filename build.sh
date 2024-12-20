out_dir="$HOME/.darkplaces/id1_tex/textures"
python -m build --output "$out_dir/"

for map in "e1m5 e1m7 e2m2 e2m3 e2m4 e2m5 e2m6 e3m3 e3m4 e4m7"
do
	mkdir -p "$out_dir/$map"/

	# Have to use some level overrides to fix plat_top1 on non-tech levels
	# because internally they have the same name
	ln -sf ../plat_top1_mx.tga "$out_dir/$map"/plat_top1.tga
	ln -sf ../plat_top1_mx_bump.tga "$out_dir/$map"/plat_top1_bump.tga
	ln -sf ../plat_top1_mx_gloss.tga "$out_dir/$map"/plat_top1_gloss.tga
done
